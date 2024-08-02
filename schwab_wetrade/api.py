import time
from schwab.client import Client
from schwab.streaming import StreamClient
from schwab.utils import EnumEnforcer
from schwab.auth import TokenMetadata
from schwab_wetrade.user_session import UserSession
from schwab_wetrade.utils import parse_response_data, log_in_background


class APIClient(Client, StreamClient):
  def __init__(self, session:UserSession=None):
    session = UserSession() if session == None else session
    api_key = session.config['api_key']
    metadata = TokenMetadata(session.session.token, int(time.time()), lambda token: None)
    Client.__init__(self, 
      api_key=api_key,
      session=session,
      enforce_enums=True,
      token_metadata=metadata)
    StreamClient.__init__(self, client=self)
    for method_name in dir(Client):
      if method_name[0] != '_' and method_name[0].isupper() == False and method_name not in dir(EnumEnforcer):
        setattr(self, method_name, self.function_wrapper(method_name))

  def function_wrapper(self, func_name):
    func = getattr(super(), func_name)
    def wrap(*args, parsed_response=False, **kwargs):
      r = func(*args, **kwargs)
      if parsed_response == True:
        log_in_background(
          called_from = func_name, 
          url = r.url,
          r = r,
          account_key = kwargs['account_hash'] if 'account_hash' in kwargs else '',
          symbol = kwargs['symbol'] if 'symbol' in kwargs else '')
        return (parse_response_data(r), r.status_code)
      return r
    return wrap