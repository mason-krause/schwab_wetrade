import time
import json
import asyncio
from schwab_wetrade.api import APIClient
from schwab_wetrade.utils import log_in_background, start_thread 

class Account:
  '''
  :param APIClient client: your :ref:`APIClient <api_client>`
  :param str account_key: (optional) manually specify your account key 
  '''
  def __init__(self, client:APIClient, account_key=''):
    self.client = client
    self.account_key = account_key if account_key else self.list_accounts()[0]['hashValue']
    self.monitoring_active = False

  def list_accounts(self):
    '''
    Provides details on all brokerage accounts connected to the active API user session
    '''
    response, status_code = self.client.get_account_numbers(parsed_response=True)
    if status_code == 200:
      return response
    else:
      log_in_background(
        called_from = 'list_accounts',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Error getting account list, retrying',
        account_key = self.account_key)
      return self.list_accounts()
    
  def view_accounts(self):
    '''
    Provides details on all brokerage accounts connected to the active API user session
    '''
    response, status_code = self.client.get_accounts(parsed_response=True)
    if status_code == 200:
      return response
    else:
      log_in_background(
        called_from = 'view_accounts',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Error getting account details, retrying',
        account_key = self.account_key)
      return self.view_accounts()

  def check_balance(self):
    '''
    Returns the balance of your account
    '''
    response, status_code = self.client.get_account(parsed_response=True, account_hash=self.account_key)
    try:
      balance = response['aggregatedBalance']['liquidationValue']
      return balance
    except Exception as e:
      log_in_background(
        called_from = 'check_balance',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Error getting account balance, retrying',
        e = e,
        account_key = self.account_key)
      return self.check_balance()
    
  def view_portfolio(self):
    '''
    Provides details for your account portfolio
    '''
    response, status_code = self.client.get_account(parsed_response=True, account_hash=self.account_key)
    try:
      portfolio = response
      return portfolio
    except Exception as e:
      log_in_background(
        called_from = 'view_portfolio',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Error getting account balance, retrying',
        e = e,
        account_key = self.account_key)
      return self.check_balance()    
    
  def get_order_history(self, start_datetime=None, end_datetime=None, marker=''):
    '''
    Provides details for all orders placed in account over specified time range
    '''
    response, status_code = self.client.get_orders_for_account(account_hash=self.account_key, from_entered_datetime=start_datetime, to_entered_datetime=end_datetime)
    try:
      order_history = response['OrdersResponse']
      return order_history
    except Exception as e:
      log_in_background(
        called_from = 'get_order_history',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Error getting account order history',
        e = e,
        account_key = self.account_key)

  async def _stream_account_updates(self):
    await self.client.login() # should we move this to APIClient.__init__?
    def handler(message):
      nonlocal self
      print(json.dumps(message, indent=2)) ##
    self.client.add_account_activity_handler(handler=handler)
    await self.client.account_activity_sub()
    while self.monitoring_active == True:
      await self.client.handle_message()
    await self.client.account_activity_unsubs()   
    # await self.client.logout()

  def _monitor_account_updates(self):
    if self.monitoring_active == False:
      self.monitoring_active = True
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)
      loop.run_until_complete(self._stream_account_updates())
      loop.close()
      self.monitoring_active = False

  def monitor_in_background(self):
    '''
    Monitors account updates using asyncio
    '''
    start_thread(self._monitor_account_updates)
