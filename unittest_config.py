# -*- coding: utf-8 -*-
"""
    glia
    ~~~~~

    Configuration for unit testing.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import logging
import os

from keyczar.keys import RsaPrivateKey

# DEBUG = True

# Define addresses
SERVER_HOST = 'app.souma'
SERVER_PORT = 24500
SERVER_NAME = "{}:{}".format(SERVER_HOST, SERVER_PORT)

SQLALCHEMY_DATABASE_URI = "sqlite:///../unittest_server.db"
TESTING = True
DEBUG = True

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

# Set secret key
try:
    with open('secret_key') as f:
        SECRET_KEY = f.read()
except IOError:
    SECRET_KEY = os.urandom(24)
    with open('secret_key', 'w') as f:
        f.write(SECRET_KEY)
