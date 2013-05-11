import os
import datetime

DEBUG = False

LOG_FORMAT = (
    '%(name)s :: %(module)s [%(pathname)s:%(lineno)d]\n' +
    '%(message)s\n')

# Define addresses
SERVER_HOST = 'glia.herokuapp.com'
SERVER_PORT = int(os.environ['PORT'])
SERVER_NAME = "{}:{}".format(SERVER_HOST, SERVER_PORT)

# Define database setup
SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']

# Load server cert
SERVER_KEY = os.environ['SERVER_PRIVATE_KEY']

SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)
