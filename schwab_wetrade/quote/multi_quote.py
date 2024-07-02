import time
import asyncio
from schwab_wetrade.api import APIClient
from schwab_wetrade.market_hours import MarketHours
from schwab_wetrade.utils import log_in_background, start_thread


class MultiQuote:
  '''
  An expanded Quote for tracking multiple securities

  :param APIClient client: your :ref:`APIClient <api_client>`
  :param tuple symbols: a tuple containing a list of symbols for up to 25 securities
  '''
  def __init__(self, client:APIClient, symbols):
    self.client = client
    self.symbols = symbols
    self.symbol_str = ','.join(self.symbols)
    self.last_prices = {}
    self.monitoring_active = False
    self.market_hours = MarketHours(client=self.client)

  def get_quote(self):
    '''
    Gets the most recent quote details for your securities
    '''
    response, status_code = self.client.get_quotes(parsed_response=True, symbols=self.symbols)
    if status_code == 200:
      return response
    else:
      log_in_background(
        called_from = 'get_quote',
        tags = ['user-message'], 
        message = time.strftime('%H:%M:%S', time.localtime()) + ': Error getting quote, retrying',
        symbol = self.symbol_str)
      time.sleep(.5)
      return self.get_quote()
    
  def get_last_price(self):
    '''
    Gets the most recent prices for all of your securities
    '''
    quote_data = self.get_quote()
    for symbol in quote_data:
      self.last_prices[symbol] = quote_data[symbol]['quote']['lastPrice'] 
    return self.last_prices

  async def _stream_quote(self): 
    await self.client.login() # should we move this to APIClient.__init__?
    def handler(message):
      nonlocal self
      for quote in message['content']:
        symbol = quote['key']
        if 'LAST_PRICE' in quote:
          self.last_prices[symbol] = quote['LAST_PRICE']
    self.client.add_level_one_equity_handler(handler=handler)
    await self.client.level_one_equity_subs(symbols=self.symbols)
    while self.monitoring_active == True and self.market_hours.market_has_closed() == False:
      await self.client.handle_message()
    await self.client.level_one_equity_unsubs(symbols=self.symbols)
    
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
  
  def wait_for_price_fall(self, symbol, target_price, then=None, args=[], kwargs={}):
    '''
    Waits for a specified security to fall below a certain price then optionally runs a callback function 

    :param str symbol: the symbol of your specified security
    :param float target_price: your set target price
    :param then: (optional) a callback function to run when price falls below target
    :param list args: a list of args for your func
    :param dict kwargs: a dict containing kwargs for your func
    '''
    if symbol in self.symbols:
      self.monitor_in_background()
      waiting = True
      while waiting and self.monitoring_active == True:
        if symbol in self.last_prices and self.last_prices[symbol] < target_price:
          waiting = False
          if then:
            then(*args, **kwargs)
        time.sleep(.2)

  def run_below_price(self, symbol, target_price, func, func_args=[], func_kwargs={}):
    '''
    Runs a callback when a specified security falls below a certain price without waiting

    :param str symbol: the symbol of your specified security
    :param float target_price: your set target price
    :param func: (optional) a callback function to run when price falls below target
    :param list func_args: a list of args for your func
    :param dict func_kwargs: a dict containing kwargs for your func
    '''
    args = [symbol, target_price, func, func_args, func_kwargs]
    start_thread(self.wait_for_price_fall, args=args)

  def wait_for_price_rise(self, symbol, target_price, then=None, args=[], kwargs={}):
    '''
    Waits for a specified security to rise above a certain price then optionally runs a callback function 

    :param str symbol: the symbol of your specified security
    :param float target_price: your set target price
    :param then: (optional) a callback function to run when price rises above target
    :param list args: a list of args for your func
    :param dict kwargs: a dict containing kwargs for your func
    '''
    if symbol in self.symbols:
      self.monitor_in_background()
      waiting = True
      while waiting and self.monitoring_active == True:
        if symbol in self.last_prices and self.last_prices[symbol] > target_price:
          waiting = False
          if then:
            then(*args, **kwargs)
        time.sleep(.2)

  def run_above_price(self, symbol, target_price, func, func_args=[], func_kwargs={}):
    '''
    Runs a callback when a specified security rises above a certain price without waiting

    :param str symbol: the symbol of your specified security
    :param float target_price: your set target price
    :param func: (optional) a callback function to run when price rises above target
    :param list func_args: a list of args for your func
    :param dict func_kwargs: a dict containing kwargs for your func
    '''
    args = [symbol, target_price, func, func_args, func_kwargs]
    start_thread(self.wait_for_price_rise, args=args)
