# -*- coding: utf-8 -*-
"""
    glia.manage
    ~~~~~

    Manage database migrations

    :copyright: (c) 2015 by Vincent Ahrend.
"""
import logging
import subprocess

from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

from glia import create_app
from nucleus.nucleus.connections import db

app = create_app()
migrate = Migrate(app, db)

manager = Manager(app)
manager.add_command('db', MigrateCommand)


@manager.command
def clearmc():
    """Flush memcache"""
    from nucleus.nucleus.connections import cache

    logging.warning("Clearing memcache...")
    cache.clear()


@manager.command
def flushredis():
    """Flush Redis"""
    logging.warning("Flushing Redis...")
    subprocess.call(["redis-cli", "flushall"])


if __name__ == '__main__':
    manager.run()
