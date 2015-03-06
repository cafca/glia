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
    '%(name)s :: %(module)s [%(filename)s:%(lineno)d] ' +
    '%(message)s')

SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)
