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
USE_DEBUG_SERVER = True
LOG_LEVEL = logging.DEBUG

# Define addresses
SERVER_HOST = 'localhost'
SERVER_PORT = 24500
SERVER_NAME = "{}:{}".format(SERVER_HOST, SERVER_PORT)

AUTH_ENABLED = False

# Define database setup

# SQLITE SETUP
# DATABASE_FILE = '../server.db'
# SQLALCHEMY_DATABASE_URI = "sqlite:///" + DATABASE_FILE

# POSTGRESQL SETUP
# Create database with psql:
# >> CREATE DATABASE glia_dev ENCODING 'utf8';
SQLALCHEMY_DATABASE_URI = "postgresql://localhost/glia_dev"

SQLALCHEMY_RECORD_QUERIES = False

# Memcache config
CACHE_TYPE = "memcached"
CACHE_MEMCACHED_SERVERS = ["127.0.0.1", ]

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

# Get sendgrid credentials
try:
    with open('sendgrid.auth', 'r') as f:
        sg_auth = f.read()
except IOError:
    logging.warning("""Sendgrid configuration could not be read. Please create
        ./sendgrid.auth file with contents 'username:password'.""")
else:
    SENDGRID_USERNAME, SENDGRID_PASSWORD = sg_auth.split(":", 1)
