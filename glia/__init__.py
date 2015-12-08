# -*- coding: utf-8 -*-
"""
    glia
    ~~~~~

    A central server for the Souma cognitive network.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import logging
import os

from blinker import Namespace
from flask import Flask
from flask.ext.compress import Compress
from flask.ext.socketio import SocketIO
from flask.ext.login import LoginManager, current_user
from flask.ext.misaka import Misaka
from flask.ext.rq import RQ
from flask_debugtoolbar import DebugToolbarExtension
from humanize import naturaltime
from humanize.time import naturaldelta
from slack_log_handler import SlackLogHandler

from .helpers import setup_loggers, ProxiedRequest, AnonymousPersona
from nucleus.nucleus.connections import db, cache
from nucleus.nucleus.models import Persona
from glia.helpers import inject_mentions, gallery_col_width, sort_hot
from worker import scheduler

socketio = SocketIO()
login_manager = LoginManager()
notification_signals = Namespace()
compress = Compress()


def create_app(log_info=True):
    """Initialize Flask app"""
    app = Flask('glia')
    app.config.from_object("default_config")
    try:
        app.config.from_envvar("GLIA_CONFIG")
    except RuntimeError:
        logging.warning("Only default_config was loaded. User the GLIA_CONFIG"
                        + " environment variable to specify additional options.")
        logging.warning('>> export GLIA_CONFIG="./development_config.py"')

    # For Heroku: ProxiedRequest replaces request.remote_addr which the real one
    # instead of their internal IP
    app.request_class = ProxiedRequest

    # Setup SQLAlchemy database
    db.init_app(app)
    with app.app_context():
        if not db.engine.dialect.has_table(db.engine.connect(), "persona"):
            import nucleus.nucleus.models
            app.logger.warning("Initializing database")
            db.create_all()

    # Setup rq / redis
    RQ(app)

    # Setup websockets
    socketio.init_app(app)

    # Setup Memcache
    cache_config = {k: app.config[k] for k in app.config.keys() if k.startswith('CACHE')}
    if app.config['HEROKU']:
        cache_config['CACHE_MEMCACHED_SERVERS'] = [os.getenv('MEMCACHIER_SERVERS')]
        cache_config['CACHE_MEMCACHED_USERNAME'] = os.getenv('MEMCACHIER_USERNAME')
        cache_config['CACHE_MEMCACHED_PASSWORD'] = os.getenv('MEMCACHIER_PASSWORD')
    cache.init_app(app, config=cache_config)

    # Setup login manager
    login_manager.init_app(app)
    login_manager.anonymous_user = AnonymousPersona
    login_manager.login_view = "web.login"
    login_manager.login_message = "Please login to continue browsing RKTIK"

    @login_manager.user_loader
    def load_user(userid):
        from nucleus.nucleus.models import User
        return User.query.get(userid)

    @app.context_processor
    def persona_context():
        """Makes active persona available in templates"""
        return dict(
            active_persona=current_user.active_persona
        )

    # Setup markdown support for templates
    Misaka(app)

    # Setup time filter
    # - Import here to avoid circular import
    from web.helpers import localtime, authorize_filter
    app.jinja_env.filters['naturaltime'] = naturaltime
    app.jinja_env.filters['naturaldelta'] = naturaldelta
    app.jinja_env.filters['localtime'] = lambda value: localtime(value, tzval=app.config["TIMEZONE"]) if value is not None else None

    # Additional template filters and extensions
    app.jinja_env.filters['mentions'] = inject_mentions
    app.jinja_env.filters['gallery_col_width'] = gallery_col_width
    app.jinja_env.filters['sort_hot'] = sort_hot
    app.jinja_env.filters['authorize'] = authorize_filter
    app.jinja_env.add_extension('jinja2.ext.do')

    # Setup debug toolbar
    # toolbar = DebugToolbarExtension()
    # toolbar.init_app(app)

    # Setup Gzip compression
    compress.init_app(app)

    from glia.web import app as web_blueprint
    app.register_blueprint(web_blueprint)

    loggers = [app.logger, web_blueprint.logger,
        logging.getLogger("nucleus"), logging.getLogger("rq.worker"),
        logging.getLogger('rq_scheduler.scheduler')]

    setup_loggers(loggers)

    if app.config.get("SLACK_WEBHOOK"):
        slack_handler = SlackLogHandler(app.config.get("SLACK_WEBHOOK"))
        slack_handler.setLevel(logging.INFO)
        for l in loggers:
            l.addHandler(slack_handler)

    if log_info:
        # Log configuration info
        app.logger.debug(
            "\n".join(["{:=^80}".format(" GLIA CONFIGURATION "),
                      "{:>12}: {}".format("host", app.config['SERVER_NAME']),
                      "{:>12}: {}".format("database", app.config['SQLALCHEMY_DATABASE_URI']),
                      "{:>12}: {}".format("config", os.environ["GLIA_CONFIG"]),
                      "{:>12}: {}".format("debug_serv", app.config["USE_DEBUG_SERVER"]), ]))

    return app
