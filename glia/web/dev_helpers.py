# -*- coding: utf-8 -*-
"""
    glia.dev_helpers
    ~~~~~

    Helpers for the development environment.

    :copyright: (c) 2015 by Vincent Ahrend.
"""
import logging

from flask.ext.httpauth import HTTPDigestAuth

#
# ----- Authentication -----
#

http_auth = HTTPDigestAuth()
http_auth_users = {
    "admin_user": "coaltarp1010",
    "testing_user": "PVi&OSpRNqRSghJ62W0@dcMAdYl#MVBx"
}


@http_auth.get_password
def get_pw(username):
    if username in http_auth_users:
        return http_auth_users.get(username)
    logging.warning("Attempted login by user not in HTTP auth user list")
    return None
