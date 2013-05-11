#!/usr/bin/python

from glia import app, db
from gevent.wsgi import WSGIServer
from sqlalchemy.exc import OperationalError

# Initialize database
if not db.engine.dialect.has_table(db.engine.connect(), "persona"):
    app.logger.info("Initializing database")
    db.create_all()

app.logger.info("Starting glia server on port {}".format(app.config['SERVER_PORT']))
glia_server = WSGIServer(('0.0.0.0', app.config['SERVER_PORT']), app)
glia_server.serve_forever()
