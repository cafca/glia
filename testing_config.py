# -*- coding: utf-8 -*-
"""
    testing_config
    ~~~~~

    Configuration for testing on the Heruko server.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import os
import datetime

from keyczar.keys import RsaPrivateKey

# Define addresses
SERVER_HOST = 'glia.herokuapp.com'
SERVER_PORT = int(os.environ['PORT'])

# On Heroku, the port bound to is not the same port the app will be accessible at from the outside
# this means that we bind to os.environ['PORT'] (>1000) but are actually visible at port 80

SERVER_NAME = SERVER_HOST

# Define database setup
SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']

# Load server cert
SERVER_KEY = RsaPrivateKey.Read(os.environ['SERVER_PRIVATE_KEY'])

# Set secret key
SECRET_KEY = os.environ['GLIA_SECRET_KEY']  

SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)
