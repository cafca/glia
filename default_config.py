# -*- coding: utf-8 -*-
"""
    default_config
    ~~~~~

    Base config object.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import datetime

DEBUG = False
USE_DEBUG_SERVER = False

SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)

TIMEZONE = 'Europe/Berlin'
