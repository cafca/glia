# -*- coding: utf-8 -*-
"""
    run_server
    ~~~~~

    Setup and run a Glia server. See glia/ directory.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
#!/usr/bin/python

from glia import app, db
from gevent.wsgi import WSGIServer
from sqlalchemy.exc import OperationalError

# Initialize database
if not db.engine.dialect.has_table(db.engine.connect(), "persona"):
    app.logger.info("Initializing database")
    db.create_all()

app.logger.info("Starting glia server on port {}".format(app.config['SERVER_PORT']))
app.logger.info("Authentification is {}".format("enabled" if app.config["AUTH_ENABLED"] else "disabled"))

if app.config['USE_DEBUG_SERVER']:
    # flask development server
    app.run(app.config['SERVER_HOST'], app.config['SERVER_PORT'])
else:
    glia_server = WSGIServer(('0.0.0.0', app.config['SERVER_PORT']), app)
    glia_server.serve_forever()
