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

from binascii import hexlify
from uuid import uuid4
from Crypto import Random
from flask import json
from flask.ext.sqlalchemy import SQLAlchemy

# Make sure that the right configuration is loaded
GLIA_CONFIG_OLD_VALUE = os.getenv("GLIA_CONFIG", "../development_config.py")
os.putenv("GLIA_CONFIG", "../unittest_config.py")

from glia import app
from glia.models import Souma

class GliaTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.db_fd, app.config["DATABASE"] = tempfile.mkstemp()
        db = SQLAlchemy(app)
        db.create_all()
        self.app = app.test_client()
        self.register_souma()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(app.config["DATABASE"])
        os.setenv("GLIA_CONFIG", GLIA_CONFIG_OLD_VALUE)

    def auth_headers(self, path, payload=""):
        """Return signed auth headers for the souma at self.souma"""
        rand = hexlify(Random.new().read(16))
        auth = self.souma.sign("".join([self.souma.id, rand, path, payload]))
        return [("Glia-Rand", rand), ("Glia-Auth", auth), ("Glia-Souma", self.souma.id)]
        
    def register_souma(self):
        """Assign a new Souma to self and register it with the Glia server"""
        self.souma = Souma(id=uuid4().hex[:32])
        self.souma.generate_keys()
        payload = json.dumps({"soumas": [self.souma.export(include=["id", "crypt_public", "sign_public"]), ]})
        path = "/v0/soumas/"
        return self.app.post(path, data=payload, content_type='application/json', headers=self.auth_headers(path, payload))

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
