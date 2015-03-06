#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
    run_server
    ~~~~~

    Setup and run a Glia server. See glia/ directory.

    :copyright: (c) 2013 by Vincent Ahrend.
"""

from gevent import monkey
monkey.patch_all()

from glia import create_app, socketio
from gevent.wsgi import WSGIServer

app = create_app()

if __name__ == '__main__':
    if app.config['USE_DEBUG_SERVER']:
        # flask development server
        socketio.run(app, host=app.config['SERVER_HOST'], port=app.config['SERVER_PORT'], use_reloader=True)
    else:
        glia_server = WSGIServer(('0.0.0.0', app.config['SERVER_PORT']), app)
        glia_server.serve_forever()
