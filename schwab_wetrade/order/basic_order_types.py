from schwab_wetrade.api import APIClient
from schwab_wetrade.account import Account
from .base_order import BaseOrder


class LimitOrder(BaseOrder):
  '''A limit order'''
  def __init__(self, client:APIClient, account:Account, symbol, action, quantity, price):
    self.order_type = 'LIMIT'
    BaseOrder.__init__(self, client, account, symbol, action, quantity, price)
    
class StopOrder(BaseOrder):
  '''A stop order'''
  def __init__(self, client:APIClient, account:Account, symbol, action, quantity, price):
    self.order_type = 'STOP'
    BaseOrder.__init__(self, client, account, symbol, action, quantity, price)

class MarketOrder(BaseOrder):
  '''A market order'''
  def __init__(self, client:APIClient, account:Account, symbol, action, quantity, price=0.0):
    self.order_type = 'MARKET'
    BaseOrder.__init__(self, client, account, symbol, action, quantity, price)
        
class StopLimitOrder(BaseOrder):
  '''A stop limit order'''
  def __init__(self, client:APIClient, account:Account, symbol, action, quantity, price):
    self.order_type = 'STOP_LIMIT'
    BaseOrder.__init__(self, client, account, symbol, action, quantity, price)