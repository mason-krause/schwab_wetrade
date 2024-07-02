# Schwab settings
login_method = 'manual' # 'auto', 'manual'
use_2fa = False # needed to disable SMS auth - requires totp_secret
config_id = 'prod'
config_options = {
  'prod':{
    'api_key': 'YOUR_API_KEY',
    'api_secret': 'YOUR_API_SECRET',
    'username': 'USERNAME',
    'password': 'PASSWORD',
    'totp_secret': 'TOTP_SECRET'}}

config = config_options[config_id]