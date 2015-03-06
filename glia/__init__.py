# -*- coding: utf-8 -*-
"""
    glia
    ~~~~~

    A central server for the Souma cognitive network.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import logging

from blinker import Namespace
from flask import Flask
from flask.ext.socketio import SocketIO
from flask.ext.login import LoginManager
from flask.ext.sqlalchemy import SQLAlchemy
from real_ip_address import ProxiedRequest
from humanize import naturaltime

from glia.helpers import setup_loggers

socketio = SocketIO()
login_manager = LoginManager()
notification_signals = Namespace()
db = SQLAlchemy()


def create_app():
    """Initialize Flask app"""
    app = Flask('glia')
    app.config.from_object("default_config")
    try:
        app.config.from_envvar("GLIA_CONFIG")
    except RuntimeError:
        logging.warning("Only default_config was loaded. User the GLIA_CONFIG"
                        + " environment variable to specify additional options.")
        logging.warning('>> export GLIA_CONFIG="./development_config.py"')

    # naturaltime allows templates to render human readable time
    app.jinja_env.filters['naturaltime'] = naturaltime

    # For Heroku: ProxiedRequest replaces request.remote_addr which the real one
    # instead of their internal IP
    app.request_class = ProxiedRequest

    # Setup SQLAlchemy database
    db.init_app(app)
    with app.app_context():
        if not db.engine.dialect.has_table(db.engine.connect(), "persona"):
            app.logger.info("Initializing database")
            db.create_all()

    # Setup websockets
    socketio.init_app(app)

    # Setup login manager
    login_manager.init_app(app)

    # from glia.models import AnonymousPersona
    # login_manager.anonymous_user = AnonymousPersona

    @login_manager.user_loader
    def load_user(userid):
        from glia.models import User
        return User.query.get(userid)

    from glia.api import app as api_blueprint
    from glia.web import app as web_blueprint
    app.register_blueprint(api_blueprint)
    app.register_blueprint(web_blueprint)

    setup_loggers([app.logger, web_blueprint.logger, api_blueprint.logger])

    # Log configuration info
    app.logger.info(
        "\n".join(["{:=^80}".format(" GLIA CONFIGURATION "),
                  "{:>12}: {}".format("host", app.config['SERVER_NAME']),
                  "{:>12}: {}".format("database", app.config['SQLALCHEMY_DATABASE_URI']), ]))

    return app
