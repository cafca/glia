#!/usr/bin/python

import datetime
import flask
import json
import logging
import sys

from base64 import b64decode
from dateutil.parser import parse as dateutil_parse
from flask import request, jsonify
from flask.ext.sqlalchemy import SQLAlchemy
from gevent.wsgi import WSGIServer
from keyczar.keys import RsaPrivateKey, RsaPublicKey
from uuid import uuid4


""" CONFIG """


ERROR = {
    1: (1, "No message type found."),
    2: (2, "No data payload found."),
    3: (3, "Persona does not exist."),
    4: (4, "Missing data for this request."),
    5: (5, "Invalid signature."),
    6: (6, "Session invalid. Please re-authenticate.")
}

DEBUG = False
USE_DEBUG_SERVER = False

SERVER_HOST = 'app.soma'
SERVER_PORT = 24500
SERVER_KEY_FILE = "./server_private.key"
DATABASE_FILE = './server.db'
SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)

SERVER_NAME = "{}:{}".format(SERVER_HOST, SERVER_PORT)
app = flask.Flask(__name__)
app.config.from_object(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + DATABASE_FILE
db = SQLAlchemy(app)

# Setup loggers
# Flask is configured to route logging events only to the console if it is in debug
# mode. This overrides this setting and enables a new logging handler which prints
# to the shell.
LOG_FORMAT = (
    '%(name)s :: %(module)s [%(pathname)s:%(lineno)d]\n' +
    '%(message)s\n')

loggers = [app.logger, logging.getLogger('synapse')]
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

for l in loggers:
    del l.handlers[:]  # remove old handlers
    l.setLevel(logging.INFO)
    l.addHandler(console_handler)
    l.propagate = False  # setting this to true triggers the root logger


def init_db():
    app.logger.info("Initializing database")
    db.create_all()


def create_server_certificate():
    """Create a new server certificate and save it to disk"""
    app.logger.info("Creating new server certificate")
    rsa = RsaPrivateKey.Generate()
    with open(SERVER_KEY_FILE, "w") as f:
        f.write(str(rsa))

# Load RSA key
try:
    with open(SERVER_KEY_FILE) as f:
        pass
        # => key file does exist
except IOError:
    create_server_certificate()

with open(SERVER_KEY_FILE) as f:
    rsa_json = f.read()
SERVER_KEY = RsaPrivateKey.Read(rsa_json)


""" MODELS """


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
        import json
        return json.dumps(self.export(exclude), indent=4)


class Persona(Serializable, db.Model):
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
    certificates = db.relationship('Certificate',
        backref='author', lazy='dynamic')

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
        return self.last_connected + SESSION_EXPIRATION_TIME

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


def session_message(data):
    """Create json response object"""

    app.logger.debug("Sending session message ({})".format(
        flask.json.dumps(data)))

    #sig = SERVER_KEY.Sign(data)

    return flask.jsonify(
        data=data,
        message_type='session',
        #signature=sig,
        timestamp=datetime.datetime.now().isoformat(),
    )


def error_message(errors):
    """Create error response"""
    app.logger.warning('{errors}'.format(
        errors="\n".join(["{}: {}".format(e[0], e[1]) for e in errors])))

    data = {
        'errors': errors,
        'timestamp': datetime.datetime.now().isoformat()
    }
    #sig = SERVER_KEY.Sign(data)

    return flask.jsonify(
        data=data,
        message_type='error',
        #signature=sig,
        timestamp=datetime.datetime.now().isoformat(),
    )


def message_errors(message):
    """Validate message"""

    errors = list()
    if 'message_type' not in message:
        errors.append(ERROR[1])
    if 'data' not in message or 'data' is None:
        errors.append(ERROR[2])
    if 'signature' in message:
        author = Persona.query.get(message['author_id'])
        if author:
            if author.verify(message['data'], message['signature']):
                app.logger.info("Correct signature on {} from {}".format(
                    message['message_type'], author))
            else:
                app.logger.error("Invalid signature on {}".format(message))
                errors.append(ERROR[5])
        else:
            app.logger.error("Could not verify signature. Missing author. [{}]".format(message))

    return errors


@app.route('/', methods=['GET'])
def index():
    """Display debug information"""
    sessions = Persona.query.all()

    return flask.render_template("server/index.html", sessions=sessions)


@app.route('/peerinfo', methods=['POST'])
def peerinfo():
    """Return address for each of submitted peer IDs"""
    peer_info = dict()
    for p_id in request.json['request']:
        p = Persona.query.get(p_id)
        if p:
            print "{}: {}:{}".format(p.username, p.host, p.port)
            peer_info[p_id] = (p.host, p.port)

    app.logger.info("Sending peer info for {} addresses.".format(len(request.json)))

    return jsonify(peer_info)


@app.route('/p/<persona_id>/', methods=['GET', 'POST'])
def persona(persona_id):
    if request.method == 'GET':
        # keep-alive (and lookup)

        p = Persona.query.get(persona_id)

        if p is None:
            app.logger.error("Persona not found: {}".format(persona_id))
            return error_message(errors=[ERROR[3], ])

        if not p.is_valid():
            app.logger.info('Session invalid: {session}.'.format(
                session=p.session_id))

            data = {
                'errors': [ERROR[6], ],
                'auth': p.auth
            }
            return session_message(data=data)

        # Keep session alive
        p.last_connected = datetime.datetime.now()
        db.session.add(p)
        db.session.commit()

        # Lookup peer hostnames
        peer_info = dict()
        certs = Certificate.query.filter_by(
            kind='lookup_authorization').filter_by(recipient=p).all()

        for cert in certs:
            p = cert.author
            peer_info[p.persona_id] = {
                "last_connected": p.last_connected.isoformat(),
                "hostname": p.hostname()
            }

        # Compile notifications
        notifications = Notification.query.filter_by(
            recipient_id=persona_id).all()

        notification_json = list()
        for notif in notifications:
            notification_json.append(notif.message_json)

        data = {
            'timeout': p.timeout().isoformat(),
            'session_id': p.session_id,
            'peer_info': peer_info,
            'notifications': notification_json
        }
        return session_message(data=data)

    elif request.method == 'POST':
        # Login

        errors = message_errors(request.json)
        if errors:
            return error_message(errors)

        data = request.json['data']
        required_fields = ['auth_signed']
        errors = list()
        for field in required_fields:
            if field not in data:
                errors.append((4, "{} ({})".format(ERROR[4][1], field)))
        if errors:
            return error_message(errors=errors)

        # Retrieve persona entry
        p = Persona.query.get(persona_id)
        if p is None:
            return error_message(errors=[ERROR[3], ])

        # Validate request auth
        is_valid = p.verify(p.auth, data['auth_signed'])
        if not is_valid:
            app.logger.error("Login failed with invalid signature.")
            return error_message(errors=[ERROR[5], ])

        # Create new session
        session_id = p.reset()
        p.last_connected = datetime.datetime.now()
        db.session.add(p)
        db.session.commit()

        data = {
            'timeout': p.timeout().isoformat(),
            'session_id': session_id,
            'errors': [],
        }
        return session_message(data=data)


@app.route('/p/<persona_id>/create', methods=['POST'])
def create_persona(persona_id):
    # Validate request
    errors = message_errors(request.json)
    if errors:
        return error_message(errors)

    # Validate request data
    data = request.json['data']
    required_fields = [
        'persona_id', 'username', 'email_hash', 'sign_public', 'crypt_public', 'reply_to']
    errors = list()
    for field in required_fields:
        if field not in data:
            errors.append((4, "{} ({})".format(ERROR[4][1], field)))

    if errors:
        return error_message(errors=errors)

    p = Persona(
        persona_id=data["persona_id"],
        username=data["username"],
        sign_public=data["sign_public"],
        crypt_public=data["crypt_public"],
        email_hash=data["email_hash"],
        host=request.remote_addr,
        port=data["reply_to"],
    )
    p.reset()
    db.session.add(p)
    db.session.commit()

    app.logger.info("New persona {} registered from {}:{}".format(
        p.persona_id, p.host, p.port))

    data = {
        'timeout': p.timeout().isoformat(),
        'session_id': p.session_id,
        'errors': [],
    }
    return session_message(data=data)


@app.route('/find-people', methods=['POST'])
def find_people():
    # Validate request
    errors = message_errors(request.json)
    if errors:
        return error_message(errors)

    # Find corresponding personas
    # TODO: Allow multiple lookups at once
    email_hash = request.json['data']['email_hash']
    p = Persona.query.filter_by(email_hash=email_hash).first()

    if p:
        # Compile response
        app.logger.info("[find people] Persona {} found".format(p))
        data = {
            'found': p.export(include=[
                "persona_id",
                "username",
                "host",
                "port",
                "crypt_public",
                "sign_public",
                "connectable"]),
        }
    else:
        app.logger.info(
            "[find people] Persona <{}> not found.".format(email_hash[:8]))
        data = None

    return session_message(data=data)


if __name__ == '__main__':
    import sys
    from sqlalchemy.exc import OperationalError

    # Initialize database
    try:
        db.session.execute("SELECT * FROM 'persona' LIMIT 1")
    except OperationalError:
        app.logger.info("Initializing database")
        db.create_all()

    if len(sys.argv) == 2 and sys.argv[1] == 'init_db':
        init_db()

    app.logger.info("Starting glia server on port {}".format(SERVER_PORT))
    local_server = WSGIServer(('', SERVER_PORT), app)
    local_server.serve_forever()
