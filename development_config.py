# -*- coding: utf-8 -*-
"""
    glia
    ~~~~~

    Configuration for development. Uses a local SQLite DB and a file `secret_key` in
    which the server RSA keys are stored

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import logging
import os

from keyczar.keys import RsaPrivateKey

DEBUG = True
LOG_LEVEL = logging.DEBUG

# Define addresses
SERVER_HOST = 'app.souma.io'
SERVER_PORT = 24500
SERVER_NAME = "{}:{}".format(SERVER_HOST, SERVER_PORT)

AUTH_ENABLED = False

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

# Set secret key
try:
    with open('secret_key', 'rb') as f:
        SECRET_KEY = f.read()
except IOError:
    SECRET_KEY = os.urandom(24)
    with open('secret_key', 'wb') as f:
        f.write(SECRET_KEY)
