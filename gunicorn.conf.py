"""Allow the AI request to finish before the web worker times out."""
import os

bind = '0.0.0.0:' + os.getenv('PORT', '10000')
workers = 1
threads = 4
timeout = 120
