# -*- coding: utf-8 -*-
"""
    run_tests.py
    ~~~~~

    Testing suite for Glia

    :copyright: (c) 2013 by Vincent Ahrend.
"""

import os
import unittest
import tempfile
import requests

from binascii import hexlify
from uuid import uuid4
from Crypto import Random
from flask import json
from flask.ext.sqlalchemy import SQLAlchemy

from glia import app, db
from glia.models import Souma

app.config.from_object("unittest_config")

class GliaTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        db.init_app(app)
        db.create_all()
        self.app = app.test_client()
        self.register_souma()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(app.config["DATABASE"])
        os.setenv("GLIA_CONFIG", GLIA_CONFIG_OLD_VALUE)

    def auth_headers(self, path, headers=dict(), payload=""):
        """Return signed auth headers for the souma at self.souma"""
        class MockRequest(object):
            headers = dict()
            url = None

        auth = GliaAuth(self.souma, payload)
        r = MockRequest()
        r.headers = headers
        r = auth(r)
        return r.headers
        
    def register_souma(self):
        """Assign a new Souma to self and register it with the Glia server"""
        self.souma = Souma(id=uuid4().hex[:32])
        self.souma.generate_keys()
        payload = json.dumps({"soumas": [self.souma.export(include=["id", "crypt_public", "sign_public"]), ]})
        path = "/v0/soumas/"
        headers = self.auth_headers(path, payload=payload)
        return self.app.post(path, data=payload, headers=headers, content_type='application/json')

    def test_register_souma(self):
        rv = self.register_souma()
        resp = json.loads(rv.data)
        assert len(resp["meta"]["errors"]) == 0

    def test_server_status(self):
        rv = self.app.get('/v0/', headers=self.auth_headers('/v0/'))
        print rv.data
        resp = json.loads(rv.data)
        assert "server_status" in resp
        assert resp["server_status"]["status_code"] == 0

    def test_find_personas(self):
        h = "0"*32  # pseude email-hash
        payload = json.dumps({"email_hash": [h, ]})
        rv = self.app.post('/v0/personas/', data=payload, content_type='application/json', headers=self.auth_headers('/v0/personas/', payload=payload))
        print rv.data
        resp = json.loads(rv.data)
        assert resp["meta"]["errors"][0] == glia.ERROR["OBJECT_NOT_FOUND"](h)


if __name__ == "__main__":
    unittest.main()
