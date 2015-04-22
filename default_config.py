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

# Don't let Flask Debug Toolbar interrupt redirects (BREAKS HTTPAUTH)
DEBUG_TB_INTERCEPT_REDIRECTS = False

SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)

TIMEZONE = 'Europe/Berlin'
