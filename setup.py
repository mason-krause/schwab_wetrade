import setuptools

# with open('README.rst', 'r') as f:
#   long_description = f.read()

setuptools.setup(
  name = 'schwab_wetrade',
  version = '0.0.1',
  author = 'Mason Krause',
  description = 'An Schwab python library built for active stock trading',
  # long_description = long_description,
  long_description_content_type='text/x-rst',
  url='https://github.com/mason-krause/schwab_wetrade',
  packages = setuptools.find_packages(),
  include_package_data = True,
  python_requires = '>=3.7',
  install_requires = [
    'schwab-py',
    'playwright',
    'pyotp',
    'google-cloud-logging', 
    'google-cloud-storage', 
    'google-cloud-secret-manager',
    'polars', 
    'pandas', 
    'pyarrow'],
    extras_require={
      'dev': [
        'pytest',
        'pytest-timeout',
        'sphinx',
        'sphinx_rtd_theme']},)