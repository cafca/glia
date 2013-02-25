#!/usr/bin/python

import datetime
import flask

from flask import request
from flask.ext.sqlalchemy import SQLAlchemy
from keyczar.keys import RsaPrivateKey
from uuid import uuid4


""" CONFIG """


ERROR = {
    1: (1, "No message type found."),
    2: (2, "No data payload found."),
    3: (3, "Persona does not exist."),
    4: (4, "Missing data for this request."),
    5: (5, "Invalid signature."),
}

DEBUG = True
USE_DEBUG_SERVER = False

SERVER_HOST = 'app.soma'
SERVER_PORT = 24500
SERVER_KEY_FILE = "./server_private.key"
DATABASE_FILE = './server.db'
SESSION_EXPIRATION_TIME = datetime.timedelta(minutes=60)

SERVER_NAME = "{}:{}".format(SERVER_HOST, SERVER_PORT)
app = flask.Flask(__name__)
app.config.from_object(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + DATABASE_FILE
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
try:
    with open(SERVER_KEY_FILE) as f:
        pass
except IOError:
    create_server_certificate()

with open(SERVER_KEY_FILE) as f:
    rsa_json = f.read()
SERVER_KEY = RsaPrivateKey.Read(rsa_json)


""" MODELS """


class Persona(db.Model):
    persona_id = db.Column(db.String(32), primary_key=True)
    session_id = db.Column(db.String(32), default=uuid4().hex)
    auth = db.Column(db.String(32), default=uuid4().hex)
    host = db.Column(db.String(128))
    port = db.Column(db.Integer)
    connectable = db.Column(db.Boolean)
    last_connected = db.Column(db.DateTime, default=datetime.datetime.now())
    sign_public = db.Column(db.Text)
    crypt_public = db.Column(db.Text)

    def is_valid(self, my_session):
        """Return True if the given session is valid"""
        if my_session != self.id:
            # Invalid session id
            return False
        elif self.timeout() > datetime.datetime.now():
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


def session_message(data):
    """Create json response object"""

    app.logger.debug("Sending session message ({})".format(
        flask.json.dumps(data, indent=4)))

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
                'errors': 'Session invalid. Please re-authenticate.',
                'auth': p.auth
            }
            return session_message(data=data)

        # Keep session alive
        p.last_connected = datetime.datetime.now()
        db.session.add(p)
        db.commit(p)

        # Lookup
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
            'session_valid': True,
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

        # Retrieve persona entry
        p = Persona.query.get(data['persona_id'])
        if p is None:
            return error_message(errors=[ERROR[3], ])

        # Create new session
        session_id = p.reset()
        db.session.add(p)
        db.session.commit(p)

        data = {
            'timeout': p.timeout().isoformat(),
            'session_id': session_id,
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
        'persona_id', 'email_hashes', 'sign_public', 'crypt_public', 'reply_to']
    errors = list()
    for field in required_fields:
        if field not in data:
            errors.append((4, "{} ({})".format(ERROR[4][1], field)))
    if errors:
        return error_message(errors=errors)

    # TODO: save email hashes
    p = Persona(
        persona_id=data["persona_id"],
        sign_public=data["sign_public"],
        crypt_public=data["crypt_public"],
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
    }
    return session_message(data=data)


@app.route('/<persona_id>/logout', methods=['POST'])
def logout(persona_id):
    """Reset the session of a persona"""
    errors = message_errors(request.json)
    if request.json['data']['logout'] != persona_id:
        errors.append(ERROR[5])
    if errors:
        return error_message(errors)

    p = Persona.query.get(persona_id)
    if p is None:
        return error_message(errors=[ERROR[3], ])
    else:
        p.reset()
        db.session.add(p)
        db.session.commit()
        return session_message(data={'auth': p.auth})


if __name__ == '__main__':
    init_db()
    app.run(SERVER_HOST, SERVER_PORT)
