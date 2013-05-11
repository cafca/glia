import json
import datetime

from base64 import b64decode
from glia import app, db
from keyczar.keys import RsaPrivateKey, RsaPublicKey
from uuid import uuid4


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

    def json(self, exclude=[]):
        """Return this object JSON encoded"""
        return json.dumps(self.export(exclude), indent=4)


class Persona(Serializable, db.Model):
    """A Persona is a user profile"""

    __tablename__ = 'persona'
    persona_id = db.Column(db.String(32), primary_key=True)
    username = db.Column(db.String(80))
    session_id = db.Column(db.String(32), default=uuid4().hex)
    auth = db.Column(db.String(32), default=uuid4().hex)
    host = db.Column(db.String(128))
    port = db.Column(db.Integer)
    connectable = db.Column(db.Boolean)
    created = db.Column(db.DateTime, default=datetime.datetime.now())
    last_connected = db.Column(db.DateTime, default=datetime.datetime.now())
    sign_public = db.Column(db.Text)
    crypt_public = db.Column(db.Text)
    email_hash = db.Column(db.String(32))
    certificates = db.relationship(
        'Certificate', backref='author', lazy='dynamic')

    def __str__(self):
        return "<{} [{}]>".format(self.username, self.persona_id)

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
    author_id = db.Column(db.String(32), db.ForeignKey('persona.persona_id'))
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
