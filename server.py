#!/usr/bin/python

import datetime
import flask

from base64 import b64decode
from dateutil.parser import parse as dateutil_parse
from flask import request
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

DEBUG = True
USE_DEBUG_SERVER = False

SERVER_HOST = 'pineal.herokuapp.com'
SERVER_PORT = 24500
SERVER_KEY_FILE = "./server_private.key"
DATABASE_FILE = './server.db'
SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=15)

SERVER_NAME = "{}:{}".format(SERVER_HOST, SERVER_PORT)
app = flask.Flask(__name__)
app.config.from_object(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)


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
rsa_json = os.environ['SERVER_PRIVATE_KEY']
SERVER_KEY = RsaPrivateKey.Read(rsa_json)


""" MODELS """


class Serializable():
    """ Make SQLAlchemy models json serializable"""
    def export(self, exclude=[]):
        """Return this object as a dict"""
        return {c.name: str(getattr(self, c.name))
            for c in self.__table__.columns if c not in exclude}

    def json(self, exclude=[]):
        """Return this object JSON encoded"""
        import json
        return json.dumps(self.export(exclude), indent=4)


class Persona(Serializable, db.Model):
    persona_id = db.Column(db.String(32), primary_key=True)
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

    def is_valid(self, my_session=None):
        """Return True if the given session is valid"""

        if my_session and my_session != self.id:
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

    return errors


@app.route('/', methods=['GET'])
def index():
    """Display debug information"""
    sessions = Persona.query.all()

    return flask.render_template("server/index.html", sessions=sessions)


@app.route('/<persona_id>/', methods=['GET', 'POST'])
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
        # The field 'lookup' may contain a list of persona-ids, separated by
        # a semicolon for which an address is requested
        lookup = dict()
        if 'lookup' in request.args:
            lookup_ids = request.args['lookup'].split(";")
            app.logger.info("Lookup requested for {} IDs".format(len(lookup_ids)))
            for lookup_id in lookup_ids:
                # TODO: Check whether the lookup has given permissions
                p = Persona.query.get(persona_id)
                if p:
                    lookup[lookup_id] = {
                        "last_connected": p.last_connected,
                        "hostname": "{}:{}".format(p.host, p.port),
                    }
                else:
                    lookup[lookup_id] = {
                        # Persona does not exist
                        "error": ERROR[3],
                    }

        data = {
            'timeout': p.timeout().isoformat(),
            'session_id': p.session_id,
            'lookup': lookup,
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


@app.route('/<persona_id>/create', methods=['POST'])
def create_persona(persona_id):
    # Validate request
    errors = message_errors(request.json)
    if errors:
        return error_message(errors)

    # Validate request data
    data = request.json['data']
    required_fields = [
        'persona_id', 'email_hash', 'sign_public', 'crypt_public', 'reply_to']
    errors = list()
    for field in required_fields:
        if field not in data:
            errors.append((4, "{} ({})".format(ERROR[4][1], field)))

    if errors:
        return error_message(errors=errors)

    p = Persona(
        persona_id=data["persona_id"],
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
    app.logger.info("Request for 1 email address lookup.")

    # Find corresponding personas
    # TODO: Allow multiple lookups at once
    email_hash = request.json['data']['email_hash']
    p = Persona.query.filter_by(email_hash=email_hash).first()

    # Compile response
    data = {
        'found': p.export(exclude=["sign_private, crypt_private"]),
    }

    return session_message(data=data)


if __name__ == '__main__':
    init_db()
    local_server = WSGIServer(('', SERVER_PORT), app)
    local_server.serve_forever()
