import datetime
import logging

from keyczar.keys import RsaPrivateKey

DEBUG = False

LOG_FORMAT = (
    '%(name)s :: %(module)s [%(pathname)s:%(lineno)d]\n' +
    '%(message)s\n')

# Define addresses
SERVER_HOST = 'app.soma'
SERVER_PORT = 24500
SERVER_NAME = "{}:{}".format(SERVER_HOST, SERVER_PORT)

# Define database setup
DATABASE_FILE = '../server.db'
SQLALCHEMY_DATABASE_URI = "sqlite:///" + DATABASE_FILE

# Load server cert
SERVER_KEY_FILE = "./server_private.key"
try:
    with open(SERVER_KEY_FILE) as f:
        rsa_json = f.read()
        SERVER_KEY = RsaPrivateKey.Read(rsa_json)
except IOError:
    logging.warning("Creating new server certificate")
    SERVER_KEY = RsaPrivateKey.Generate()
    with open(SERVER_KEY_FILE, "w") as f:
        f.write(str(SERVER_KEY))

SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)
