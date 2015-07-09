# -*- coding: utf-8 -*-
"""
    glia.dev_helpers
    ~~~~~

    Helpers for the development environment.

    :copyright: (c) 2015 by Vincent Ahrend.
"""
import logging
import os

from flask.ext.httpauth import HTTPDigestAuth

#
# ----- Authentication -----
#

http_auth = HTTPDigestAuth()

if os.environ.get('RK_HTTPAUTH_ADMIN') is None:
    # Fallback for local dev environment
    logging.warning("Using hardcoded HTTPAuth credentials")
    http_auth_users = {
        "admin_user": "coaltarp1010",  # mm so nice to type
        "testing_user": "PVi&OSpRNqRSghJ62W0@dcMAdYl#MVBx"
    }
else:
    http_auth_users = {
        "admin_user": os.environ['RK_HTTPAUTH_ADMIN'],
        "testing_user": os.environ['RK_HTTPAUTH_USER']
    }


@http_auth.get_password
def get_pw(username):
    if username in http_auth_users:
        logging.info("HTTPAuth: {} authenticated".format(username))
        return http_auth_users.get(username)
    logging.warning("Attempted login by user not in HTTP auth user list")
    return None
