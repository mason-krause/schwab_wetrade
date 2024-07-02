import time
import datetime
import pickle
import google.cloud.storage
import polars as pl 
import pandas as pd
from .quote import Quote
from schwab_wetrade.api import APIClient
from schwab_wetrade.utils import log_in_background
try:
  import settings
except ModuleNotFoundError:
  import schwab_wetrade.project_template.settings as settings


class DataFrameQuote(Quote):
  '''
  A Quote that uses a DataFrame to keep track of quote details and enable complex calculations

  :param APIClient client: your :ref:`APIClient <api_client>`
  :param str symbol: the symbol of your security
  '''
  def __init__(self, client:APIClient, symbol):
    Quote.__init__(self, client, symbol)
    self.data = pl.DataFrame(schema={ #maybe use numpy array instead of polars df
      'datetime': pl.Datetime,
      'datetime_epoch': pl.Int64,
      'ask': pl.Float64,
      'ask_size': pl.Int64,
      'ask_time': pl.Datetime,
      'bid': pl.Float64,
      'bid_size': pl.Int64,
      'bid_time': pl.Datetime,
      'last_trade': pl.Float64,
      'last_trade_size': pl.Int64,
      'last_trade_time': pl.Datetime,
      '30s_average': pl.Float64,
      '10s_average': pl.Float64})
    self.smoothed_price = 0.0

  async def _stream_quote(self):
    await self.client.login() # should we move this to APIClient.__init__?
    def handler(message):
      nonlocal self
      content = message['content'][0]
      if 'LAST_PRICE' in content: # update price first
        self.last_price = last_trade = content['LAST_PRICE']
      else:
        last_trade = self.data[-1, 'last_trade']
      self.data.extend(pl.DataFrame({    
        'datetime': datetime.datetime.fromtimestamp(message['timestamp']/1000),
        'datetime_epoch': message['timestamp'],
        'ask': content['ASK_PRICE'] if 'ASK_PRICE' in content else self.data[-1, 'ask'],
        'ask_size': content['ASK_SIZE'] if 'ASK_SIZE' in content else self.data[-1, 'ask_size'],
        'ask_time': datetime.datetime.fromtimestamp(content['ASK_TIME_MILLIS']/1000) if 'ASK_TIME_MILLIS' in content else self.data[-1, 'ask_time'],
        'bid': content['BID_PRICE'] if 'BID_PRICE' in content else self.data[-1, 'bid'],
        'bid_size': content['BID_SIZE'] if 'BID_SIZE' in content else self.data[-1, 'bid_size'],
        'bid_time': datetime.datetime.fromtimestamp(content['BID_TIME_MILLIS']/1000) if 'BID_TIME_MILLIS' in content else self.data[-1, 'bid_time'],
        'last_trade': last_trade,
        'last_trade_size': content['LAST_SIZE'] if 'LAST_SIZE' in content else self.data[-1, 'last_trade_size'],
        'last_trade_time': datetime.datetime.fromtimestamp(content['TRADE_TIME_MILLIS']/1000) if 'TRADE_TIME_MILLIS' in content else self.data[-1, 'last_trade_time'],
        '30s_average': 0.0,
        '10s_average': 0.0}))
      self.data = self.data.set_sorted('datetime').with_columns([
        pl.col('last_trade').rolling_mean_by(by='datetime', window_size='30s', closed='both').alias('30s_average'),
        pl.col('last_trade').rolling_mean_by(by='datetime', window_size='10s', closed='both').alias('10s_average')])
      self.smoothed_price = self.data[-1, '10s_average']
    self.client.add_level_one_equity_handler(handler=handler)
    await self.client.level_one_equity_subs(symbols=[self.symbol])
    while self.monitoring_active == True and self.market_hours.market_has_closed() == False:
      await self.client.handle_message()
    await self.client.level_one_equity_unsubs(symbols=[self.symbol])
    # await self.client.logout()

  def export_data(self):
    '''
    Exports a DataFrame containing your quote data as a .pkl file saved to *./export/data*
    '''
    filename = datetime.datetime.today().strftime('%Y_%m_%d') + '-' + self.ticker
    df = self.data.to_pandas()
    df.to_pickle('./export/data/{}.pkl'.format(filename))

  def upload_quote_data(self):
    '''
    Uploads a DataFrame to a Google Cloud Storage bucket specified in :ref:`settings.py <settings>`
    '''
    if hasattr(settings, 'quote_bucket'):
      log_in_background(
        called_from = 'upload_quote_data',
        tags = ['user-message'], 
        message = '{}: Uploading quote data to Google Cloud'.format(
          datetime.datetime.now().strftime('%H:%M:%S')))
      filename = datetime.datetime.today().strftime('%Y_%m_%d') + '-' + self.ticker
      df = self.data.to_pandas()
      storage_client = google.cloud.storage.Client()
      bucket = storage_client.bucket(settings.quote_bucket)
      blob = bucket.blob(filename)
      with blob.open(mode='wb') as f:
        pickle.dump(df, f)

  def get_pd_data(self):
    '''
    Returns a pandas DataFrame containing your quote data
    '''
    return self.data.to_pandas()