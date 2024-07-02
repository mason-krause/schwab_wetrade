import time
import datetime
from zoneinfo import ZoneInfo
from schwab_wetrade.api import APIClient
from schwab_wetrade.utils import log_in_background
from schwab.client import Client


class MarketHours:
  '''
  :param str date_str: (optional) manually set date (format: '%Y-%m-%d')
  '''
  def __init__(self, client:APIClient, date_str=''):
    self.client = client
    self.date = datetime.datetime.today() if date_str=='' else datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    self.date_str = date_str if date_str != '' else datetime.datetime.strftime(self.date, '%Y-%m-%d')
    self.est = ZoneInfo('US/Eastern')
    self.open = None
    self.close = None
    self._set_market_hours()

  def check_market_hours(self):
    response, status_code = self.client.get_market_hours(parsed_response=True, markets=Client.MarketHours.Market.EQUITY, date=self.date)
    if status_code == 200:
      if 'EQ' not in response['equity']: # market is closed
        open = None
        close = None
      else:
        open = response['equity']['EQ']['sessionHours']['regularMarket'][0]['start']
        close = response['equity']['EQ']['sessionHours']['regularMarket'][0]['end']
      return (open, close)
    
  def change_date(self, new_date_str):
    self.date_str = new_date_str
    self.date = datetime.datetime.strptime(self.date_str, '%Y-%m-%d').date()
    self._set_market_hours()
  
  def _set_market_hours(self):
    open, close = self.check_market_hours()
    if open == None: # in case you change_date('%Y-%m-%d')
      self.open == None
      self.close == None
    else:
      self.open = datetime.datetime.strptime(open, '%Y-%m-%dT%H:%M:%S%z')
      self.close = datetime.datetime.strptime(close, '%Y-%m-%dT%H:%M:%S%z')
      
  def market_has_closed(self) -> bool:
    if self.close == None:
      log_in_background(
        called_from = 'market_has_closed',
        tags = ['user-message'], 
        message = '{}: Markets are closed today ({})'.format(
          time.strftime('%H:%M:%S', time.localtime()),
          self.date_str))
      return True
    elif datetime.datetime.now(self.est) < self.close:
      return False
    else:
      log_in_background(
        called_from = 'market_has_closed',
        tags = ['user-message'], 
        message = '{}: Markets are closed for the day'.format(
          time.strftime('%H:%M:%S', time.localtime())))
      return True  
        
  def market_has_opened(self) -> bool:
    if self.open == None:
      log_in_background(
        called_from = 'market_has_opened',
        tags = ['user-message'], 
        message = '{}: Markets are closed today ({})'.format(
          time.strftime('%H:%M:%S', time.localtime()),
          self.date_str))
      return False
    elif datetime.datetime.now(self.est) > self.open:
      return True
    else:
      return False
    
  def seconds_till_close(self):
    if self.close != None:
      now = datetime.datetime.now(self.est)
      return (self.close - now).total_seconds()
    
  def seconds_till_open(self):
    if self.open != None:
      now = datetime.datetime.now(self.est)
      return (self.open - now).total_seconds()

  def wait_for_market_open(self):
    if self.open == None:
      return
    now = datetime.datetime.now(self.est)
    if self.open > now:
      log_in_background(
        called_from = 'wait_for_market_open',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Waiting for market to open')
      time.sleep((self.open - now).total_seconds())
  
  def now_est(self):
    return datetime.datetime.now(self.est)