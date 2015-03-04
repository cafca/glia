# -*- coding: utf-8 -*-
"""
    glia
    ~~~~~

    A central server for the Souma cognitive network.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import logging
import sys

from blinker import Namespace
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.socketio import SocketIO
from flask.ext.login import LoginManager
from real_ip_address import ProxiedRequest
from humanize import naturaltime

# Initialize Flask app
app = Flask('glia')
app.config.from_object("default_config")
try:
    app.config.from_envvar("GLIA_CONFIG")
except RuntimeError:
    logging.warning("Only default_config was loaded. User the GLIA_CONFIG"
                    + " environment variable to specify additional options.")
    logging.warning('>> export GLIA_CONFIG="../development_config.py"')

# naturaltime allows templates to render human readable time
app.jinja_env.filters['naturaltime'] = naturaltime

# For Heroku: ProxiedRequest replaces request.remote_addr which the real one
# instead of their internal IP
app.request_class = ProxiedRequest

# Setup SQLAlchemy database
db = SQLAlchemy(app)

# Setup Blinker namespace
notification_signals = Namespace()

# Setup websockets
socketio = SocketIO()
socketio.init_app(app)

# Setup login manager
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(userid):
    from glia.models import User
    return User.query.get(userid)

# Setup loggers
# Flask is configured to route logging events only to the console if it is in debug
# mode. This overrides this setting and enables a new logging handler which prints
# to the shell.
loggers = [app.logger, ]
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(logging.Formatter(app.config['LOG_FORMAT']))

for l in loggers:
    del l.handlers[:]  # remove old handlers
    l.setLevel(logging.DEBUG)
    l.addHandler(console_handler)
    l.propagate = False  # setting this to true triggers the root logger

# Log configuration info
app.logger.info(
    "\n".join(["{:=^80}".format(" GLIA CONFIGURATION "),
              "{:>12}: {}".format("host", app.config['SERVER_NAME']),
              "{:>12}: {}".format("database", app.config['SQLALCHEMY_DATABASE_URI']), ]))

# Views need to be imported at the bottom to avoid circular import (see Flask docs)
import glia.views
import glia.myelin
