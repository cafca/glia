# -*- coding: utf-8 -*-
"""
    run_tests.py
    ~~~~~

    Testing suite for Glia

    :copyright: (c) 2013 by Vincent Ahrend.
"""

import os
import unittest
import logging

from binascii import hexlify
from Crypto import Random
from uuid import uuid4
from flask import json

from glia import create_app
from glia.helpers import setup_loggers
from nucleus.nucleus import ERROR

# Make sure that the right configuration is loaded
GLIA_CONFIG_OLD_VALUE = os.getenv("GLIA_CONFIG", "../development_config.py")


base_url = "https://app.souma:24500"


logger = logging.getLogger('unittest')
setup_loggers([logger, ])


class GliaTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["GLIA_CONFIG"] = "../unittest_config.py"
        app = create_app(log_info=False)

        self.app = app.test_client()

        logger.info("Generating new Souma keypairs")
        self.register_souma()

    def tearDown(self):
        os.remove("./unittest_server.db")
        os.environ["GLIA_CONFIG"] = GLIA_CONFIG_OLD_VALUE

    def auth_headers(self, path, payload=""):
        """Return signed auth headers for the souma at self.souma"""
        rand = hexlify(Random.new().read(16))
        auth = self.souma.sign("".join([self.souma.id, rand, path, payload]))
        return [("Glia-Rand", rand), ("Glia-Auth", auth), ("Glia-Souma", self.souma.id)]

    def register_souma(self):
        """Assign a new Souma to self and register it with the Glia server"""
        from nucleus.nucleus.models import Souma

        self.souma = Souma(id=uuid4().hex[:32])
        self.souma.generate_keys()
        payload = json.dumps({"soumas": [self.souma.export(include=["id", "crypt_public", "sign_public"]), ]})
        path = "/v0/soumas/"
        return self.app.post(path, data=payload, content_type='application/json', base_url=base_url)

    def test_register_souma(self):
        rv = self.register_souma()
        resp = json.loads(rv.data)
        assert len(resp["meta"]["errors"]) == 0

    def test_server_status(self):
        logger.info("Testing server status page")
        rv = self.app.get('/v0/', base_url=base_url, headers=self.auth_headers('/v0/'))
        print rv.data
        resp = json.loads(rv.data)
        assert "server_status" in resp
        assert resp["server_status"][0]["status_code"] == 0

    def test_find_personas(self):
        h = "0" * 32  # pseude email-hash
        payload = json.dumps({"email_hash": [h, ]})
        rv = self.app.post('/v0/personas/',
            data=payload,
            content_type='application/json',
            base_url=base_url,
            headers=self.auth_headers('/v0/', payload=payload))

        print rv.data
        resp = json.loads(rv.data)
        assert resp["meta"]["errors"][0][0] == ERROR["OBJECT_NOT_FOUND"](h)[0]
        assert resp["meta"]["errors"][0][1] == ERROR["OBJECT_NOT_FOUND"](h)[1]


if __name__ == "__main__":
    unittest.main()
