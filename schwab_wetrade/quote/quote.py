import time
import asyncio
from schwab_wetrade.api import APIClient
from schwab_wetrade.market_hours import MarketHours
from schwab_wetrade.utils import log_in_background, start_thread


class Quote:
  '''
  A simple Quote for tracking one security

  :param APIClient client: your :ref:`APIClient <api_client>`
  :param str symbol: the symbol of your security
  '''
  def __init__(self, client:APIClient, symbol):
    self.client = client
    self.symbol = symbol
    self.last_price = 0.0
    self.monitoring_active = False
    self.market_hours = MarketHours(client=self.client)

  def get_quote(self):
    '''
    Gets the most recent quote details for your security
    '''
    response, status_code = self.client.get_quote(parsed_response=True, symbol=self.symbol)
    if status_code == 200:
      return response
    else:
      log_in_background(
        called_from = 'get_quote',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Error getting quote, retrying',
        symbol = self.symbol)
      time.sleep(.5)
      return self.get_quote()
    
  def get_open(self):
    '''
    Returns the opening price for your security during the current session
    '''
    quote = self.get_quote()
    if self.symbol in quote:
      return quote[self.symbol]['quote']['openPrice']
    
  def get_last_price(self):
    '''
    Gets the most recent price for your security
    '''
    quote = self.get_quote()
    if self.symbol in quote:
      return quote[self.symbol]['quote']['lastPrice']

  async def _stream_quote(self): 
    await self.client.login() # should we move this to APIClient.__init__?
    def handler(message):
      nonlocal self
      if 'LAST_PRICE' in message['content'][0]:
        self.last_price = message['content'][0]['LAST_PRICE']
    self.client.add_level_one_equity_handler(handler=handler)
    await self.client.level_one_equity_subs(symbols=[self.symbol])
    while self.monitoring_active == True and self.market_hours.market_has_closed() == False:
      await self.client.handle_message()
    await self.client.level_one_equity_unsubs(symbols=[self.symbol])
    # await self.client.logout()
    
  def _monitor_quote(self):
    if self.monitoring_active == False:
      if self.market_hours.market_has_closed() == False:
        self.monitoring_active = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._stream_quote())
        loop.close()
        self.monitoring_active = False

  def monitor_in_background(self):
    '''
    Monitors quote details using asyncio to keep Quote.last_price up to date 
    '''
    start_thread(self._monitor_quote)
  
  def wait_for_price_fall(self, target_price, then=None, args=[], kwargs={}):
    '''
    Waits for your security to fall below a certain price then optionally runs a callback function 

    :param float target_price: your set target price
    :param then: (optional) a callback function to run when price falls below target
    :param list args: a list of args for your func
    :param dict kwargs: a dict containing kwargs for your func
    '''
    self.monitor_in_background()
    waiting = True
    while waiting and self.monitoring_active == True:
      if self.last_price!=0.0 and self.last_price < target_price:
        waiting = False
        if then:
          then(*args, **kwargs)
      time.sleep(.2)

  def run_below_price(self, target_price, func, func_args=[], func_kwargs={}):
    '''
    Runs a callback when your security falls below a certain price without waiting

    :param float target_price: your set target price
    :param func: a function to run when price falls below target
    :param list func_args: a list of args for your func
    :param dict func_kwargs: a dict containing kwargs for your func
    '''
    args = [target_price, func, func_args, func_kwargs]
    start_thread(self.wait_for_price_fall, args=args)

  def wait_for_price_rise(self, target_price, then=None, args=[], kwargs={}):
    '''
    Waits for your security to rise above a certain price then optionally runs a callback function 

    :param float target_price: your set target price
    :param then: (optional) a callback function to run when price rises above target
    :param list args: a list of args for your func
    :param dict kwargs: a dict containing kwargs for your func
    '''
    self.monitor_in_background()
    waiting = True
    while waiting and self.monitoring_active == True:
      if self.last_price!=0.0 and self.last_price > target_price:
        waiting = False
        if then:
          then(*args, **kwargs)
      time.sleep(.2)

  def run_above_price(self, target_price, func, func_args=[], func_kwargs={}):
    '''
    Runs a callback when your security rises above a certain price without waiting

    :param float target_price: your set target price
    :param func: a function to run when price rises above target
    :param list func_args: a list of args for your func
    :param dict func_kwargs: a dict containing kwargs for your func
    '''
    args = [target_price, func, func_args, func_kwargs]
    start_thread(self.wait_for_price_rise, args=args)
