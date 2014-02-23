# -*- coding: utf-8 -*-
"""
    glia.models
    ~~~~~

    Defines models for all data permanently stored in the glia.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import json
import datetime

from base64 import b64decode, urlsafe_b64decode, urlsafe_b64encode
from keyczar.keys import RsaPrivateKey, RsaPublicKey
from uuid import uuid4
from sqlalchemy.orm import backref

from glia import app, db


class Serializable():
    """ Make SQLAlchemy models json serializable"""
    def export(self, exclude=[], include=None):
        """Return this object as a dict"""
        if include:
            return {field: str(getattr(self, field))
                for field in include}
        else:
            return {c.name: str(getattr(self, c.name))
                for c in self.__table__.columns if c not in exclude}

    def json(self, exclude=[], include=None):
        """Return this object JSON encoded"""
        return json.dumps(self.export(exclude=exclude, include=include), indent=4)


class Persona(Serializable, db.Model):
    """A Persona is a user profile"""

    __tablename__ = 'persona'
    id = db.Column(db.String(32), primary_key=True)
    username = db.Column(db.String(80))
    session_id = db.Column(db.String(32), default=uuid4().hex)
    auth = db.Column(db.String(32), default=uuid4().hex)
    host = db.Column(db.String(128))
    port = db.Column(db.Integer)
    connectable = db.Column(db.Boolean)
    created = db.Column(db.DateTime, default=datetime.datetime.now())
    modified = db.Column(db.DateTime)
    last_connected = db.Column(db.DateTime, default=datetime.datetime.now())
    sign_public = db.Column(db.Text)
    crypt_public = db.Column(db.Text)
    email_hash = db.Column(db.String(64))

    # TODO: Enable starmap when using p2p
    # starmap = db.relationship('DBVesicle',
    #     primaryjoin="dbvesicle.c.id==persona.c.starmap_id")
    # starmap_id = db.Column(db.String(32), db.ForeignKey('dbvesicle.id'))

    certificates = db.relationship(
        'Certificate', backref='author', lazy='dynamic')

    def __str__(self):
        return "<Persona '{}' [{}]>".format(self.username.encode('utf-8'), self.id)

    def controlled(self):
        """Return True if Persona has private signing and encryption keys

        Returns:
            Boolean: True if self has private keys
        """
        if self.sign_private is None:
            return False
        elif self.crypt_private is None:
            return False
        else:
            return True

    def is_valid(self, my_session=None):
        """Return True if the given session is valid"""

        if my_session and my_session != self.session_id:
            # Invalid session id
            return False

        if self.timeout() > datetime.datetime.now():
            return True
        else:
            # Session has expired
            self.reset()
            db.session.add(self)
            db.session.commit()
            return False

    def reset(self):
        """Reset session_id"""
        self.session_id = uuid4().hex
        self.auth = uuid4().hex
        return self.session_id

    def hostname(self):
        """Return hostname in host:port format"""
        return "{host}:{port}".format(host=self.host, port=self.port)

    def timeout(self):
        return self.last_connected + app.config['SESSION_EXPIRATION_TIME']

    def verify(self, data, signature_b64):
        """ Verify a signature using RSA """

        signature = b64decode(signature_b64)
        key_public = RsaPublicKey.Read(self.sign_public)
        return key_public.Verify(data, signature)


class Certificate(db.Model, Serializable):
    """Certificates authorize actions specified by the kind field"""
    id = db.Column(db.String(32), primary_key=True)
    kind = db.Column(db.String(32))
    recipient_id = db.Column(db.String(32))
    recipient = db.relationship('Persona', uselist=False)
    author_id = db.Column(db.String(32), db.ForeignKey('persona.id'))
    json = db.Column(db.Text)

    def __init__(self, kind, recipient, json):
        from uuid import uuid4
        self.id = uuid4().hex
        self.kind = kind
        self.recipient = recipient
        self.json = json


class Notification(db.Model):
    """Store messages for delayed delivery"""
    notification_id = db.Column(db.String(32), primary_key=True)
    recipient_id = db.Column(db.String(32))
    message_json = db.Column(db.Text)

    def __init__(self, recipient_id, message_json):
        from uuid import uuid4
        self.notification_id = uuid4().hex
        self.recipient_id = recipient_id
        self.message_json = message_json


class Souma(Serializable, db.Model):
    """A physical machine in the Souma network"""

    __tablename__ = "souma"
    id = db.Column(db.String(32), primary_key=True)

    crypt_private = db.Column(db.Text)
    crypt_public = db.Column(db.Text)
    sign_private = db.Column(db.Text)
    sign_public = db.Column(db.Text)

    def __str__(self):
        return "<Souma [{}]>".format(self.id[:6])

    def generate_keys(self):
        """ Generate new RSA keypairs for signing and encrypting. Commit to DB afterwards! """

        # TODO: Store keys encrypted
        rsa1 = RsaPrivateKey.Generate()
        self.sign_private = str(rsa1)
        self.sign_public = str(rsa1.public_key)

        rsa2 = RsaPrivateKey.Generate()
        self.crypt_private = str(rsa2)
        self.crypt_public = str(rsa2.public_key)

    def authentic_request(self, request):
        """Return true if a request carries a valid signature"""
        glia_rand = b64decode(request.headers["Glia-Rand"])
        glia_auth = request.headers["Glia-Auth"]
        app.logger.debug("Authenticating {}\nID: {}\nRand: {}\nPath: {}\nPayload: {}".format(request, str(self.id), glia_rand, request.url, request.data))
        req = "".join([str(self.id), glia_rand, str(request.url), request.data])
        return self.verify(req, glia_auth)

    def encrypt(self, data):
        """ Encrypt data using RSA """

        if self.crypt_public == "":
            raise ValueError("Error encrypting: No public encryption key found for {}".format(self))

        key_public = RsaPublicKey.Read(self.crypt_public)
        return key_public.Encrypt(data)

    def decrypt(self, cypher):
        """ Decrypt cyphertext using RSA """

        if self.crypt_private == "":
            raise ValueError("Error decrypting: No private encryption key found for {}".format(self))

        key_private = RsaPrivateKey.Read(self.crypt_private)
        return key_private.Decrypt(cypher)

    def sign(self, data):
        """ Sign data using RSA """
        if self.sign_private == "":
            raise ValueError("Error signing: No private signing key found for {}".format(self))

        key_private = RsaPrivateKey.Read(self.sign_private)
        signature = key_private.Sign(data)
        return urlsafe_b64encode(signature)

    def verify(self, data, signature_b64):
        """ Verify a signature using RSA """
        if self.sign_public == "":
            raise ValueError("Error verifying: No public signing key found for {}".format(self))

        # Signature arrives unicode formatted, encode in utf-8 to turn into
        # a byte string that urlsafe_b64decode can digest.
        # http://stackoverflow.com/questions/2229827/django-urlsafe-base64-decoding-with-decryption
        signature_b64_bytes = signature_b64.encode("utf-8")

        signature = urlsafe_b64decode(signature_b64_bytes)
        key_public = RsaPublicKey.Read(self.sign_public)
        return key_public.Verify(data, signature)

keycrypt = db.Table('keycrypts',
    db.Column('dbvesicle_id', db.String(32), db.ForeignKey('dbvesicle.id')),
    db.Column('recipient_id', db.String(32), db.ForeignKey('persona.id'))
)

class DBVesicle(db.Model):
    """Store the representation of a Vesicle"""

    __tablename__ = "dbvesicle"
    id = db.Column(db.String(32), primary_key=True)
    json = db.Column(db.Text)
    created = db.Column(db.DateTime, default=datetime.datetime.now())
    modified = db.Column(db.DateTime)
    author_id = db.Column(db.String(32))

    recipients = db.relationship('Persona',
        secondary='keycrypts',
        primaryjoin="keycrypts.c.dbvesicle_id==dbvesicle.c.id",
        secondaryjoin="keycrypts.c.recipient_id==persona.c.id",
        backref=backref('inbox', lazy='dynamic'))
