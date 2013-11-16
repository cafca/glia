# -*- coding: utf-8 -*-
"""
    default_config
    ~~~~~

    Base config object.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import datetime
import logging

DEBUG = False

LOG_FORMAT = (
    '%(name)s :: %(module)s [%(pathname)s:%(lineno)d]\n' +
    '%(message)s\n')

SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)
