import time
import os
import json
import threading
import authlib.integrations.base_client.errors as authlib_errors
from pyotp import TOTP
from contextlib import suppress
from playwright.sync_api import sync_playwright
from authlib.integrations.httpx_client import OAuth2Client
from schwab.auth import client_from_manual_flow, client_from_token_file
from schwab_wetrade.utils import log_in_background
try: 
  import settings
except ModuleNotFoundError:
  import schwab_wetrade.project_template.settings as settings

def write_token(token, token_path):
  if token_path != '':
    with open(token_path, 'w') as f:
      content = {
        'creation_timestamp': int(time.time()),
        'token': token }
      json.dump(content, f) # not overwriting existing files?

def get_redirect_url(authorize_url, config={}):
  config = settings.config if config == {} else config
  headless_login = settings.headless_login if hasattr(settings, 'headless_login') else True
  if settings.use_2fa == True:
    totp = TOTP(config['totp_secret'])
  with sync_playwright() as p:    
    log_in_background(
      called_from = 'get_redirect_url',
      tags = ['user-message'], 
      message = time.strftime('%H:%M:%S', time.localtime()) + ': Logging in')
    try:
      browser = p.firefox.launch(headless=headless_login)
      page = browser.new_page()
      page.goto(authorize_url)
      page.wait_for_timeout(1000)
      page.locator('#loginIdInput').fill(config['username'])
      page.locator('#passwordInput').fill(config['password'])
      page.locator('#btnLogin').click()
      if settings.use_2fa == True:
        page.wait_for_url('https://sws-gateway.schwab.com/ui/host/#/placeholder')
        page.locator('#placeholderCode').fill(totp.now())
        page.locator('#continueButton').click()
      page.wait_for_url('https://sws-gateway.schwab.com/ui/host/#/third-party-auth/cag', timeout=4000)
      page.locator('#acceptTerms').click()
      page.locator('#submit-btn').click()
      page.locator('#agree-modal-btn-').click()
      page.wait_for_url('https://sws-gateway.schwab.com/ui/host/#/third-party-auth/account')
      page.locator('#submit-btn').click()
      page.wait_for_url('https://sws-gateway.schwab.com/ui/host/#/third-party-auth/confirmation')
      page.locator('#cancel-btn').click()
      url = ''
      while '127.0.0.1' not in url:
        url = page.evaluate('() => window.location.href')
        time.sleep(.1)
      browser.close()
      log_in_background(
        called_from = 'get_redirect_url',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Login successful')
      return url
    except Exception as e: # close browser even if there's an exception
      browser.close()
      log_in_background(
        called_from = 'get_redirect_url',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Login failed',
        e = e)
      return

def new_session(config={}, new_token=False):
  config = settings.config if config == {} else config
  token_path = settings.token_path if hasattr(settings, 'token_path') else ''
  if new_token == False and token_path and os.path.isfile(token_path):
    log_in_background(
      called_from = 'new_session',
      tags = ['user-message'], 
      message = time.strftime('%H:%M:%S', time.localtime()) + ': Creating new session from token file')
    client = client_from_token_file(
      token_path=token_path,
      api_key = config['api_key'],
      app_secret = config['api_secret'])
    return client.session
  if settings.login_method == 'manual':
    client = client_from_manual_flow(
      api_key = config['api_key'],
      app_secret = config['api_secret'],
      callback_url = 'https://127.0.0.1',
      token_path = token_path)
    return client.session
  else:
    client = OAuth2Client(
      client_id = config['api_key'],
      client_secret = config['api_secret'],
      redirect_uri = 'https://127.0.0.1')
    authorize_url, state = client.create_authorization_url(
          'https://api.schwabapi.com/v1/oauth/authorize')
    redirect_url = get_redirect_url(authorize_url, config={})
    if redirect_url == None:
      return new_session(config=config)
    token = client.fetch_token(
      url = 'https://api.schwabapi.com/v1/oauth/token',
      authorization_response = redirect_url,
      client_id = config['api_key'], 
      auth= (config['api_key'], config['api_secret']))
    if token_path != '':
      write_token(token, token_path)
    return client
  
class UserSession:
  def __init__(self, config={}):
    self.config = settings.config if config == {} else config
    self.session = None
    self.logged_in = False
    self.token_bucket = TokenBucket(capacity=120, refill_rate=2) # 120 requests/min 
    # self.request_queue = ThreadPoolExecutor(max_workers=4)
    self.login()

  def renew_token(self): # doesn't work? 
    token_path = settings.token_path if hasattr(settings, 'token_path') else ''
    try:
      self.session.refresh_token('https://api.schwabapi.com/v1/oauth/token')
      if token_path != '':
        write_token(self.session.token, token_path)
      return self.session.token
    except Exception as e:
      log_in_background(
        called_from = 'UserSession.renew_token',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Could not renew token; check logs',
        e = e)

  def login(self, new_token=False):
    self.logged_in = False
    try:
      self.session = new_session(self.config, new_token)
      self.logged_in = True
    except Exception as e:
      log_in_background(
        called_from = 'login',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Error, retrying login',
        e = e)
      self.login(new_token)

  def post(self, *args, **kwargs):
    return self.handle_request('POST', args, kwargs)
      
  def get(self, *args, **kwargs):
    return self.handle_request('GET', args, kwargs)

  def put(self, *args, **kwargs):
    return self.handle_request('PUT', args, kwargs)
  
  # def queue_request(self, http_method, args, kwargs):
  #   self.resume_event.wait()
  #   future = self.request_queue.submit(self.handle_request, http_method, args, kwargs)
  #   wait([future])
  #   return future.result()

  def handle_request(self, http_method, args, kwargs):
    if self.logged_in:
      url = kwargs['url'] if 'url' in kwargs else ''
      while not self.token_bucket.consume():
        time.sleep(.5)
      try:
        r = self.session.request(http_method, *args, **kwargs, timeout=30)
      except authlib_errors.OAuthError as e:
        log_in_background(
          called_from = 'UserSession.handle_request',
          tags = ['user-message'], 
          message = time.strftime('%H:%M:%S', time.localtime()) + ': OAuth error, creating new User Session',
          e = e)
        self.login(new_token=True)
        return self.handle_request(http_method, args, kwargs)
      except Exception as e:
        # print(e)
        error_num = 0
        error_msg = ''
        with suppress(Exception):
          error_num = e.args[0].args[1].errno
          error_msg = e.args[0].args[1].message
        log_in_background(
          called_from = 'UserSession.handle_request',
          tags = ['user-message', 'connection-unknown'], 
          message = time.strftime('%H:%M:%S', time.localtime()) + ': Error making request, check logs',
          url = url,
          e = e) 
      if r.status_code == 429: # Too many requests, wait then replace
        log_in_background(
          called_from = 'UserSession.handle_request',
          tags = ['user-message'], 
          message = time.strftime('%H:%M:%S', time.localtime()) + ': Too Schwab API requests, pausing requests for 30 sec')
        self.token_bucket.freeze_refill(30.0) # maybe change bucket.refill_rate instead
        return self.handle_request(http_method, args, kwargs)
      if r.status_code == 403: # Access denied; should get a new token
        log_in_background(
          called_from = 'UserSession.handle_request',
          tags = ['user-message'], 
          message = time.strftime('%H:%M:%S', time.localtime()) + ': API Auth error, resolve with Schwab')
        # get a new token 
      return r

class TokenBucket:
  def __init__(self, capacity, refill_rate):
    self.capacity = capacity
    self.tokens = capacity
    self.refill_rate = refill_rate
    self.last_check = time.time()
    self.freeze_until = 0
    self.lock = threading.Lock()

  def _refill(self):
    now = time.time()
    if now < self.freeze_until:
      self.last_check = now
      return
    elapsed = now - self.last_check
    new_tokens = elapsed * self.refill_rate
    self.tokens = min(self.capacity, self.tokens + new_tokens)
    self.last_check = now

  def consume(self, tokens=1):
    with self.lock:
      self._refill()
      if self.tokens >= tokens:
        self.tokens -= tokens
        return True
      return False
  
  def freeze_refill(self, seconds):
    self.freeze_until = max(self.freeze_until, time.time() + seconds)