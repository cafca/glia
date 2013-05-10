#!/usr/bin/python

import sys
import os

# Add parent directory of current working directory to path so the current
# directory can be imported as a module (I have no idea why this is neccessary).
cwd_parent_dir = os.sep.join(os.getcwd().split(os.sep)[:-1])
sys.path.append(cwd_parent_dir)

from glia import app, db
from gevent.wsgi import WSGIServer
from sqlalchemy.exc import OperationalError

# Initialize database
try:
    db.session.execute("SELECT * FROM 'persona' LIMIT 1")
except OperationalError:
    app.logger.info("Initializing database")
    db.create_all()

app.logger.info("Starting glia server on port {}".format(app.config['SERVER_PORT']))
glia_server = WSGIServer(('', app.config['SERVER_PORT']), app)
glia_server.serve_forever()
