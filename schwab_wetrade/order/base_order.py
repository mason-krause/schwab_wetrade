import time
import random
from contextlib import suppress
from schwab_wetrade.api import APIClient
from schwab_wetrade.account import Account
from schwab_wetrade.utils import start_thread, log_in_background

class BaseOrder:
  '''
  A base order class containing methods use in other order types

  :param APIClient client: your :ref:`APIClient <api_client>`
  :param str account: an Account() object
  :param str symbol: the symbol of your security
  :param str action: The action for your order (BUY, SELL, BUY_TO_COVER, SELL_SHORT, BUY_OPEN, BUY_CLOSE, SELL_OPEN, SELL_CLOSE, EXCHANGE)
  :param int quantity: the quantity for your order
  :param float price: the price for your order
  '''
  def __init__(self, client:APIClient, account:Account, symbol, action, quantity, price):
    self.client = client
    self.account = account
    self.symbol = symbol
    self.action = action
    self.quantity = quantity
    self.price = price
    self.order_type = self.order_type if hasattr(self, 'order_type') else 'LIMIT'
    self.security_type = self.security_type if hasattr(self, 'security_type') else 'EQUITY'
    self.order_id = 0
    self.updating = False
    self.status = ''
    self.disable_await_status = False
    self.subscribed = False

  def generate_order_payload(self):
    return {
      'session': 'NORMAL',
      'duration': 'DAY',
      'orderType': self.order_type,
      'price': self.price,
      'orderLegCollection': [{
        'instruction': self.action,
        'instrument': {
          'assetType': self.security_type,
          'symbol': self.symbol},
        'quantity': self.quantity}],
      'orderStrategyType': 'SINGLE'}
  
  def place_order(self):
    '''Places your order'''
    # response, status_code = self.client.place_order(account_hash=self.account.account_key, order_spec=self.generate_order_payload())
    r = self.client.place_order(account_hash=self.account.account_key, order_spec=self.generate_order_payload())
    if r.status_code == 201:
      location = r.headers.get('location', '')
      if location != '':
        self.order_id = location.split('/orders/')[1]
        log_in_background(
          called_from = 'place_order',
          tags = ['user-message'], 
          account_key = self.account.account_key,
          symbol = self.symbol,
          message = '{}: Placed {} order to {} {} shares of {} at ${} (Order ID: {}, Account: {})'.format(
            time.strftime('%H:%M:%S', time.localtime()),
            self.order_type,
            self.action,
            self.quantity,
            self.symbol,
            self.price,
            self.order_id,
            self.account.account_key[:8]))
        return True
    return False

  def create_subscription(self):
    if self.subscribed == False and self.order_id != 0:
      self.check_status() # check current status
      self.account.add_order_subscription(self)
      self.subscribed = True
      start_thread(self._delayed_check_status, args=[5]) # check status again in case something happened while subscribing

  def cancel_subscription(self):
    self.account.remove_order_subscription(self.order_id, deactivate_monitoring=False)
    self.subscribed = False

  def place_and_subscribe(self):
    if self.place_order() == True:
      self.create_subscription()

  def _delayed_check_status(self, delay:int):
    time.sleep(delay)
    self.check_status()

  def check_status(self):
    '''Checks the status of an already placed order'''
    response, status_code = self.client.get_order(parsed_response=True, order_id=self.order_id, account_hash=self.account.account_key)
    # response, status_code = self.client.get_order(parsed_response=True, order_id=self.order_id, account_hash=self.account.account_key, symbol=self.symbol) can log symbol if update schwab_py.BaseClient.get_order(add * after args) why does parsed_response work though
    if status_code == 200:
      status = self.status = response['status']
      if status == 'EXECUTED':
        self.price = response['price']
      return status
 
  def cancel_order(self):
    '''Cancels your active, already-placed order'''
    # response, status_code = self.client.   
    
  def _handle_rejected_order(self):
    log_in_background(
      called_from = '_handle_rejected_order',
      tags = ['user-message'], 
      account_key = self.account.account_key,
      symbol = self.symbol,
      message = '{}: Order {} REJECTED - no longer waiting (Account: {})'.format(time.strftime('%H:%M:%S', time.localtime()), self.order_id, self.account.account_key[:8]))
    
  def wait_for_status(self, status, then=None, args=[], kwargs={}):
    '''
    Waits for your order to reach your specified status then runs an optional callback function
    Need to run create_subscription() in order to keep order status updated live
    
    :param str status: the status to wait for (OPEN, EXECUTED, CANCELED, INDIVIDUAL_FILLS, CANCEL_REQUESTED, EXPIRED, REJECTED)
    :param then: (optional) a callback function to run after waiting for status
    :param list args: a list of args for your function
    :param dict kwargs: a dict containing kwargs for your function
    '''
    self.create_subscription() # subscribe if not already subscribed
    waiting = True if self.order_id != 0 else False
    stop_for = ('CANCELED','EXECUTED','EXPIRED')
    while waiting and self.disable_await_status == False:
      if self.updating == False:
        if self.status in (*stop_for, 'REJECTED', status):
          self.cancel_subscription()
        if self.status == 'REJECTED': # special handling for rejected orders
          return self._handle_rejected_order()
        if self.status == status:
          if then:
            return then(*args, **kwargs)
          else:
            return
        elif self.status in stop_for:
          log_in_background(
            called_from = 'wait_for_status',
            tags = ['user-message'], 
            account_key = self.account_key,
            symbol = self.symbol,
            message = '{}: Order # {} {} - no longer waiting (Account: {})'.format(time.strftime('%H:%M:%S', time.localtime()), self.order_id, self.status, self.account.account_key[:8]))
          return
      time.sleep(.2)