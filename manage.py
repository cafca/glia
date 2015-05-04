# -*- coding: utf-8 -*-
"""
    glia.manage
    ~~~~~

    Manage database migrations

    :copyright: (c) 2015 by Vincent Ahrend.
"""
from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

from glia import create_app
from nucleus.nucleus.database import db

app = create_app()
migrate = Migrate(app, db)

manager = Manager(app)
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
