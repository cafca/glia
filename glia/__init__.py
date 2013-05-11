import logging
import sys
import os

from blinker import Namespace
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from humanize import naturaltime
from werkzeug.contrib.cache import SimpleCache

ERROR = {
    1: (1, "No message type found."),
    2: (2, "No data payload found."),
    3: (3, "Persona does not exist."),
    4: (4, "Missing data for this request."),
    5: (5, "Invalid signature."),
    6: (6, "Session invalid. Please re-authenticate.")
}

# Initialize Flask app
app = Flask('glia')
app.config.from_object("default_config")
try:
    app.config.from_envvar("GLIA_CONFIG")
except RuntimeError:
    logging.warning("Only default_config was loaded. User the GLIA_CONFIG"
                    + " environment variable to specify additional options.")

app.jinja_env.filters['naturaltime'] = naturaltime

# Setup SQLAlchemy database
db = SQLAlchemy(app)

# Setup Blinker namespace
notification_signals = Namespace()

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