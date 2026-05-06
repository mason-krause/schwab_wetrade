import time
import random
from contextlib import suppress
from schwab_wetrade.api import APIClient
from schwab_wetrade.account import Account
from schwab_wetrade.utils import start_thread, log_in_background

class MultiOrder:
  '''
  A base order class for ordering multiple securities at once

  :param APIClient client: your :ref:`APIClient <api_client>`
  :param str account: an Account() object
  :param str symbol: the symbol of your security
  :param str action: The action for your order (BUY, SELL, BUY_TO_COVER, SELL_SHORT, BUY_OPEN, BUY_CLOSE, SELL_OPEN, SELL_CLOSE, EXCHANGE)
  :param int quantity: the quantity for your order
  :param float price: the price for your order
  '''
  def __init__(self, client:APIClient, account:Account, action, symbol_quantities:dict):
    self.client = client
    self.account = account
    self.action = action
    self.symbol_quantities = symbol_quantities
    self.order_type = self.order_type if hasattr(self, 'order_type') else 'MARKET'
    self.security_type = self.security_type if hasattr(self, 'security_type') else 'EQUITY'
    self.order_id = 0
    self.updating = False
    self.status = ''
    self.disable_await_status = False
    self.subscribed = False

  def generate_order_payload(self):
    order_legs = []
    for symbol, quantity in self.symbol_quantities.items():
      order_legs.append({
       'instruction': self.action,
        'instrument': {
          'assetType': self.security_type,
          'symbol': symbol},
        'quantity': quantity})
    return {
      'session': 'NORMAL',
      'duration': 'DAY',
      'orderType': self.order_type,
      # 'price': self.price,
      'orderLegCollection': order_legs,
      'orderStrategyType': 'SINGLE'}
  
  def place_order(self):
    '''Places your order'''
    r = self.client.place_order(account_hash=self.account.account_key, order_spec=self.generate_order_payload())
    if r.status_code == 201:
      location = r.headers.get('location', '')
      if location != '':
        self.order_id = location.split('/orders/')[1]
        log_in_background(
          called_from = 'place_order',
          tags = ['user-message'], 
          account_key = self.account.account_key,
          symbol = self.symbol_quantities,
          message = '{}: Placed {} order to {} shares of {} (Order ID: {}, Account: {})'.format(
            time.strftime('%H:%M:%S', time.localtime()),
            self.order_type,
            self.action,
            str(self.symbol_quantities),
            self.order_id,
            self.account.account_key[:8]))
        return True
    message = ''
    with suppress(Exception):
      message = r.json()['message']
    log_in_background(
      called_from = 'place_order',
      tags = ['user-message'], 
      account_key = self.account.account_key,
      symbol = self.symbol_quantities,
      message = '{}: Error: {} Could not place {} order to {} shares of {} (Order ID: {}, Account: {})'.format(
        time.strftime('%H:%M:%S', time.localtime()),
        message,
        self.order_type,
        self.action,
        str(self.symbol_quantities),
        self.order_id,
        self.account.account_key[:8]))
    return False