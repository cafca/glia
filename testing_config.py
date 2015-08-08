# -*- coding: utf-8 -*-
"""
    testing_config
    ~~~~~

    Configuration for testing on the Heruko server.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import datetime
import logging
import os

from keyczar.keys import RsaPrivateKey

# On Heroku, the port bound to is not the same port the app will be accessible at from the outside
# this means that we bind to os.environ['PORT'] (>1000) but are actually visible at port 80
SERVER_HOST = 'dev.rktik.com'
SERVER_PORT = int(os.environ['PORT'])
AUTH_ENABLED = bool(os.environ['SOUMA_AUTH'])
HEROKU = True

DEBUG = True
LOG_LEVEL = logging.DEBUG

# Memcache
CACHE_TYPE = 'spreadsaslmemcachedcache'

SERVER_NAME = SERVER_HOST

# Define database setup
SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']

# Load server cert
SERVER_KEY = RsaPrivateKey.Read(os.environ['SERVER_PRIVATE_KEY'])

# Set secret key
SECRET_KEY = os.environ['GLIA_SECRET_KEY']

SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)

AMPLITUDE_API_KEY = os.getenv("AMPLITUDE_API_KEY", None)
