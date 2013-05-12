import os
import datetime

from keyczar.keys import RsaPrivateKey

# Define addresses
SERVER_HOST = 'glia.herokuapp.com'
SERVER_PORT = int(os.environ['PORT'])
# SERVER_NAME = "{}:{}".format(SERVER_HOST, SERVER_PORT)
SERVER_NAME = SERVER_HOST

# Define database setup
SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']

# Load server cert
SERVER_KEY = RsaPrivateKey.Read(os.environ['SERVER_PRIVATE_KEY'])

SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)
