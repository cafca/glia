#!/usr/bin/python

import gevent
import datetime
import sys
import umemcache

from dateutil.parser import parse as dateutil_parse
from flask import abort, Flask, json, request, flash, g, redirect, render_template, url_for, session
from flask.ext.wtf import Form, TextField as WTFTextField, SelectField as WTFSelectField, Required, Email
from flask.ext.sqlalchemy import SQLAlchemy, models_committed
from gevent.wsgi import WSGIServer
from gevent.pool import Pool
from humanize import naturaltime
from keyczar.keys import RsaPrivateKey, RsaPublicKey
from sqlalchemy.exc import OperationalError
from werkzeug.local import LocalProxy
from werkzeug.contrib.cache import SimpleCache

""" Config """

DEBUG = True
USE_DEBUG_SERVER = False

SEND_FILE_MAX_AGE_DEFAULT = 1
# TODO: Generate after installation, keep secret.
SECRET_KEY = '\xae\xac\xde\nIH\xe4\xed\xf0\xc1\xb9\xec\x08\xf6uT\xbb\xb6\x8f\x1fOBi\x13'
#pw: jodat
PASSWORD_HASH = '8302a8fbf9f9a6f590d6d435e397044ae4c8fa22fdd82dc023bcc37d63c8018c'

SERVER_HOST = 'app.soma'
try:
    SERVER_PORT = int(sys.argv[1])
except IndexError:
    SERVER_PORT = 5000
SERVER_NAME = "{}:{}".format(SERVER_HOST, SERVER_PORT)
MEMCACHED_ADDRESS = "{}:{}".format(SERVER_HOST, 24000)
PEERMANAGER_PORT = SERVER_PORT + 50

app = Flask(__name__)
app.config.from_object(__name__)
app.jinja_env.filters['naturaltime'] = naturaltime


# Setup SQLAlchemy
DATABASE = 'khemia_{}.db'.format(SERVER_PORT)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + DATABASE
db = SQLAlchemy(app)


class Serializable():
    """ Make SQLAlchemy models json serializable"""
    def json(self, exclude=[]):
        import json
        return json.dumps({c.name: str(getattr(self, c.name))
            for c in self.__table__.columns if c not in exclude}, indent=4)


# Setup Document Types
class Persona(Serializable, db.Model):
    id = db.Column(db.String(32), primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    crypt_private = db.Column(db.Text)
    crypt_public = db.Column(db.Text)
    sign_private = db.Column(db.Text)
    sign_public = db.Column(db.Text)
    starmap = db.relationship('Star', backref=db.backref('creator'))
    modified = db.Column(db.DateTime, default=datetime.datetime.now(), onupdate=datetime.datetime.now())

    def __init__(self, id, username, email, sign_private=None, sign_public=None, crypt_private=None, crypt_public=None):
        self.id = id
        self.username = username
        self.email = email
        self.sign_private = sign_private
        self.sign_public = sign_public
        self.crypt_private = crypt_private
        self.crypt_public = crypt_public

    def get_absolute_url(self):
        return url_for('persona', id=self.id)

    def generate_keys(self, password):
        """ Generate new RSA keypairs for signing and encrypting. Commit to DB afterwards! """

        # TODO: Store keys encrypted

        # Generate and store keys
        app.logger.info("Generating encryption key pair for Persona {username} ({id})".format(
            username=self.username, id=self.id))

        rsa1 = RsaPrivateKey.Generate()
        self.sign_private = str(rsa1)
        self.sign_public = str(rsa1.public_key)

        app.logger.info("Generating signature key pair for Persona {username} ({id})".format(
            username=self.username, id=self.id))

        rsa2 = RsaPrivateKey.Generate()
        self.crypt_private = str(rsa2)
        self.crypt_public = str(rsa2.public_key)

    def encrypt(self, data):
        """ Encrypt data using RSA """

        key_public = RsaPublicKey.Read(self.crypt_public)
        return key_public.Encrypt(data)

    def decrypt(self, cypher):
        """ Decrypt cyphertext using RSA """

        key_private = RsaPrivateKey.Read(self.crypt_private)
        return key_private.Decrypt(cypher)

    def sign(self, data):
        """ Sign data using RSA """

        key_private = RsaPrivateKey.Read(self.crypt_private)
        return key_private.Sign(data)

    def verify(self, data, signature):
        """ Verify a signature using RSA """

        key_public = RsaPublicKey.Read(self.crypt_public)
        return key_public.Verify(data, signature)


class Star(Serializable, db.Model):
    id = db.Column(db.String(32), primary_key=True)
    text = db.Column(db.Text)
    created = db.Column(db.DateTime, default=datetime.datetime.now())
    modified = db.Column(db.DateTime, default=datetime.datetime.now(), onupdate=datetime.datetime.now())
    creator_id = db.Column(db.String(32), db.ForeignKey('persona.id'))

    def __init__(self, id, text, creator):
        self.id = id
        self.text = text
        self.creator_id = creator

    def get_absolute_url(self):
        return url_for('star', id=self.id)

# Setup Cache
cache = SimpleCache()


""" DB code """


def init_db():
    try:
        Persona.query.first()
    except OperationalError:
        app.logger.info("Initializing DB")
        db.create_all()

        # Generate test persona #1
        pv = Persona('247a1ca474b04a248c751d0eebf9738f', 'cievent', 'nichte@gmail.com')
        pv.generate_keys('jodat')
        db.session.add(pv)

        # Generate test persona #2
        paul = Persona('6e345777ca1a49cd8d005ac5e2f37cac', 'paul', 'mail@vincentahrend.com')
        paul.generate_keys('jodat')
        db.session.add(paul)

        db.session.commit()


def get_active_persona():
    """ Return the currently active persona or 0 if there is no controlled persona. """

    if 'active persona' not in session or session['active_persona'] is None:
        controlled_personas = Persona.query.filter('sign_private != ""')

        if controlled_personas.first() == None:
            return ""
        else:
            session['active_persona'] = controlled_personas.first().id

    return session['active_persona']


def logged_in():
    return cache.get('password') is not None


@app.context_processor
def persona_context():
    return dict(controlled_personas=Persona.query.filter('sign_private != ""'))


@app.before_request
def before_request():
    # TODO: serve favicon.ico
    if request.base_url[-3:] == "ico":
        abort(404)

    setup_url = "/".join(["http:/", app.config['SERVER_NAME'], "setup"])
    login_url = "/".join(["http:/", app.config['SERVER_NAME'], "login"])

    session['active_persona'] = get_active_persona()

    if app.config['PASSWORD_HASH'] == None and request.base_url != setup_url:
        app.logger.info("Redirecting to Setup")
        return redirect(url_for('setup', _external=True))

    if request.base_url not in [setup_url, login_url] and not logged_in():
        app.logger.info("Redirecting to Login")
        return redirect(url_for('login', _external=True))


@app.teardown_request
def teardown_request(exception):
    pass

""" Views """


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Display a login form and create a session if the correct pw is submitted"""
    from Crypto.Protocol.KDF import PBKDF2
    from hashlib import sha256

    error = None
    if request.method == 'POST':
        # TODO: Is this a good idea?
        salt = app.config['SECRET_KEY']
        pw_submitted = PBKDF2(request.form['password'], salt)

        if sha256(pw_submitted).hexdigest() != app.config['PASSWORD_HASH']:
            error = 'Invalid password'
        else:
            cache.set('password', pw_submitted, 3600)
            flash('You are now logged in')
            return redirect(url_for('universe'))
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    cache.set('password', None)
    flash('You were logged out')
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    from Crypto.Protocol.KDF import PBKDF2
    from hashlib import sha256

    error = None
    if request.method == 'POST':
        logged_in()
        if request.form['password'] is None:
            error = 'Please enter a password'
        else:
            salt = app.config['SECRET_KEY']
            password = PBKDF2(request.form['password'], salt)
            app.config['PASSWORD_HASH'] = sha256(password).hexdigest()
            cache.set('password', password, 3600)
            return redirect(url_for('universe'))
    return render_template('setup.html', error=error)


@app.route('/p/<id>/')
def persona(id):
    """ Render home view of a persona """

    persona = Persona.query.filter_by(id=id).first_or_404()
    starmap = Star.query.filter_by(creator_id=id)[:4]

    vizier = Vizier([
        [1, 5, 6, 2],
        [1, 1, 6, 4],
        [7, 1, 2, 2],
        [7, 3, 2, 2],
        [7, 5, 2, 2]])

    return render_template('persona.html',
        layout="persona",
        vizier=vizier,
        starmap=starmap,
        persona=persona)


class Create_persona_form(Form):
    """ Generate form for creating a persona """
    name = WTFTextField('Name', validators=[Required(), ])
    email = WTFTextField('Email (optional)', validators=[Email(), ])


@app.route('/p/create', methods=['GET', 'POST'])
def create_persona():
    """ Render page for creating new persona """
    from uuid import uuid4
    from Crypto.PublicKey import RSA
    from base64 import b64encode

    form = Create_persona_form()
    if form.validate_on_submit():
        # This is a unique ID which identifies the persona across all contexts
        uuid = uuid4().hex

        # Save persona to DB
        p = Persona(
            uuid,
            request.form['name'],
            request.form['email'])

        # Create keypairs
        p.generate_keys(cache.get('password'))

        db.session.add(p)
        db.session.commit()

        flash("New persona {} created!".format(p.username))
        return redirect(url_for('persona', id=uuid))

    return render_template('create_persona.html',
        form=form,
        next=url_for('create_persona'))


@app.route('/p/<id>/activate', methods=['GET'])
def activate_persona(id):
    """ Activate a persona """
    p = Persona.query.filter_by(id=id).first()
    if not p:
        flash("That is not you!")
    session['active_persona'] = id


class Create_star_form(Form):
    """ Generate form for creating a star """
    # Choices of the creator field need to be set before displaying the form
    # TODO: Validate creator selection
    creator = WTFSelectField('Creator', validators=[Required(), ])
    text = WTFTextField('Content', validators=[Required(), ])


@app.route('/s/create', methods=['GET', 'POST'])
def create_star():
    from uuid import uuid4
    """ Create a new star """

    controlled_personas = Persona.query.filter(Persona.sign_private != None).all()
    creator_choices = [(p.id, p.username) for p in controlled_personas]

    form = Create_star_form(default_creator=session['active_persona'])
    form.creator.choices = creator_choices
    if form.validate_on_submit():
        uuid = uuid4().hex

        new_star = Star(
            uuid,
            request.form['text'],
            request.form['creator'])
        db.session.add(new_star)
        db.session.commit()

        flash('New star created!')

        app.logger.info('Created new star {}'.format(new_star.id))
        return redirect(url_for('star', id=uuid))
    return render_template('create_star.html', form=form, controlled_personas=controlled_personas)


@app.route('/s/<id>/delete', methods=["GET"])
def delete_star(id):
    """ Delete a star """
    # TODO: Should only accept POST instead of GET
    # TODO: Check permissions
    # TODO: Create deletion request
    # TODO: Distribute deletion request

    # Delete instance from db
    s = Star.query.filter_by(id=id).first_or_404()
    db.session.delete(s)
    db.session.commit()

    app.logger.info("Deleted star {}".format(id))

    return redirect(url_for('debug'))


@app.route('/')
def universe():
    """ Render the landing page """
    stars = Star.query.all()

    vizier = Vizier([
        [1, 1, 6, 4],
        [1, 5, 4, 2],
        [5, 5, 2, 2],
        [7, 1, 2, 5]
    ])

    return render_template('universe.html', layout="sternenhimmel", constellation=stars, vizier=vizier)


@app.route('/s/<id>/', methods=['GET'])
def star(id):
    """ Display a single star """
    star = Star.query.filter_by(id=id).first_or_404()
    creator = Persona.query.filter_by(id=id)

    return render_template('star.html', layout="star", star=star, creator=creator)


@app.route('/debug/')
def debug():
    """ Display raw data """
    stars = Star.query.all()
    personas = Persona.query.all()

    return render_template('debug.html', stars=stars, personas=personas)


class Vizier():
    def __init__(self, layout):
        from collections import defaultdict

        cells = defaultdict(list)
        for e in layout:
            x_pos = e[0]
            y_pos = e[1]
            x_size = e[2]
            y_size = e[3]

            for col in xrange(x_pos, x_pos + x_size):
                for row in xrange(y_pos, y_pos + y_size):
                    if col in cells and row in cells[col]:
                        app.logger.info("Double binding of cell ({x},{y})".format(x=col, y=row))
                    else:
                        cells[col].append(row)

        self.layout = layout
        self.index = 0

    def get_cell(self):
        """ Return the next free cell's class name """
        if len(self.layout) <= self.index:
            app.logger.warning("Not enough layout cells provided for content.")
            return "hidden"

        class_name = "col{c} row{r} w{width} h{height}".format(
            c=self.layout[self.index][0],
            r=self.layout[self.index][1],
            width=self.layout[self.index][2],
            height=self.layout[self.index][3])

        self.index += 1
        return class_name


class Message(object):
    """ Container for peer messages"""

    # THIS CLASS IS WIP AND CURRENTLY NOT USED

    def __init__(self, message_type, reply_to, data, data_type):
        self.message_type = message_type
        self.reply_to = reply_to
        self.data = data
        self.data_type = data_type
        self.timestamp = None
        self.send_attributes = ["message_type", "reply_to", "data", "data_type"]

    def json():
        """Return json encoded message"""
        message = dict()
        for attr in self.send_attributes:
            message[attr] = getattr(self, attr)
        message["timestamp"] = datetime.datetime.now().isoformat()


class PeerManager(gevent.server.DatagramServer):
    """ Handle connections to peers """

    def __init__(self, address):
        gevent.server.DatagramServer.__init__(self, address)
        self.logger = app.logger
        self.message_pool = Pool(10)
        self.source_format = lambda address: "{host}:{port}".format(host=address[0], port=address[1])

        # Subscribe to database modifications
        models_committed.connect(self.on_models_committed)

        self.update_peer_list()

    def request_object(self, object_type, object_id, source_address):
        """ Request an object from a peer """
        from gevent import socket

        app.logger.info("Requesting {object_type} {object_id} from {source}".format(
            object_type=object_type, object_id=object_id, source=self.source_format(source_address)))

        # Construct request
        message = dict()
        message["message_type"] = "object_request"
        message["object_type"] = object_type
        message["object_id"] = object_id
        message["port"] = PEERMANAGER_PORT
        message_json = json.dumps(message)

        # Send request
        sock = socket.socket(type=socket.SOCK_DGRAM)
        sock.connect(source_address)
        sock.send(message_json)

    def handle(self, data, address):
        """ Handle incoming messages """
        if len(data) == 0:
            self.logger.info("[{}] Empty message received".format(address[0]))
        else:
            self.logger.debug("[{source}] {json}".format(source=self.source_format(address), json=data))
            self.socket.sendto('Received {} bytes'.format(len(data)), address)

            # TODO: Check authenticy of message
            # TODO: Attempt correcting time of message by comparing machine clocks in the message
            #   (see bittorrent utp spec)

            # Try parsing the message
            try:
                message = json.loads(data)
            except ValueError, e:
                app.logger.error("[{source}] {error}".format(source=self.source_format(address), error=e))
                return

            # Parse address of peermanager on the other end
            source_address = (address[0], message["port"])

            # Allowed message types
            message_types = [
                "change_notification",
                "object_request",
                "object",
                "inventory_request",
                "inventory"
            ]

            # Pass on the message depending on message type
            if message["message_type"] in message_types:
                handler = getattr(self, "handle_{message_type}".format(message_type=message["message_type"]))
                handler(message, source_address)

    def handle_change_notification(self, message, address):
        """ Delete or download the object the notification was about if that is neccessary """

        # Verify message
        # TODO: Check authenticity and authority
        change = message["change"]
        object_type = message["object_type"]
        object_id = message["object_id"]
        change_time = dateutil_parse(message["change_time"])

        # Load object if it exists
        if object_type == "Star":
            o = Star.query.get(object_id)
        elif object_type == "Persona":
            o = Persona.query.get(object_id)

        # TODO: Update inventory db

        # Reflect changes if neccessary
        if change == "delete":
            if o is None:
                app.logger.info("[{source}] {object_type} {object_id} deleted (no local copy)".format(
                    source=self.source_format(address), object_type=object_type, object_id=object_id))
            else:
                db.session.delete(o)
                db.session.commit()
                app.logger.info("[{source}] {object_type} {object_id} deleted".format(
                    source=self.source_format(address), object_type=object_type, object_id=object_id))

        elif change == "insert":
            # Object already exists locally
            if o is not None:
                app.logger.info("[{source}] New {object_type} {object_id} already exists.".format(
                    source=self.source_format(address), object_type=object_type, object_id=object_id))
                return

            # Request object
            app.logger.info("[{source}] New {object_type} {object_id} available".format(
                source=self.source_format(address), object_type=object_type, object_id=object_id))
            # TODO: Check if we even want to have this thing, also below in update
            self.request_object(object_type, object_id, address)

        elif change == "update":
            app.logger.info("[{source}] Updated {object_type} {object_id} available".format(
                source=self.source_format(address), object_type=object_type, object_id=object_id))
            if o is None:
                self.request_object(object_type, object_id, address)
            else:
                # Check if this is a newer version
                if o.modified < change_time:
                    self.request_object(object_type, object_id, address)
                else:
                    app.logger.debug("[{source}] Updated {object_type} {object_id} is obsolete \
                        (Remote modified: {remote} Local modified: {local}".format(
                        source=self.source_format(address), object_type=object_type,
                        object_id=object_id, remote=change_time, local=o.modified))

    def handle_inventory(self, message, address):
        """ Look through an inventory to see if we want to download some of it """
        pass

    def handle_inventory_request(self, message, address):
        """ Send an inventory to the given address """
        pass

    def handle_object(self, message, address):
        """ Handle a received download """
        # Validate response
        # TODO: Decryption
        object_type = message["object_type"]
        try:
            obj = json.loads(message["object_data"])
        except ValueError, e:
            app.logger.error("Error decoding response: {}".format(e))

        # Handle answer
        # TODO: Handle updates
        if object_type == "Star":
            o = Star(obj["id"], obj["text"], obj["creator_id"])
        elif object_type == "Persona":
            # private key is not assumed
            o = Persona(
                id=obj["id"],
                username=obj["username"],
                email=obj["email"],
                sign_public=obj["sign_public"],
                crypt_public=obj["crypt_public"],
            )
        db.session.add(o)
        db.session.commit()
        app.logger.info("[{source}] Added new {object_type} {object_id}".format(
            source=self.source_format(address), object_type=object_type, object_id=obj['id']))

    def handle_object_request(self, message, address):
        """ Serve an object to address in response to a request """
        from gevent import socket

        # Validate request
        object_type = message["object_type"]
        object_id = message["object_id"]

        # Load object
        if object_type == "Star":
            obj = Star.query.get(object_id)
        elif object_type == "Persona":
            obj = Persona.query.get(object_id)

        if obj is None:
            # TODO: Serve error message
            self.socket.sendto(str(), address)
            return

        # Construct response
        message = dict()
        message["port"] = PEERMANAGER_PORT
        message["message_type"] = "object"
        # Don't send private keys of personas
        message["object_data"] = obj.json(exclude=["sign_private, crypt_private"])
        message["object_type"] = object_type
        message_json = json.dumps(message)

        # Send response
        sock = socket.socket(type=socket.SOCK_DGRAM)
        sock.connect(address)
        sock.send(message_json)
        app.logger.info("Sent {object_type} {object_id} to {address} ({len} bytes)".format(
            object_type=object_type, object_id=object_id, address=self.source_format(address), len=len(message_json)))

    def inventory(self):
        """ Return inventory of all data stored on this machine in json format """

        # CURRENTLY NOT IN USE

        stars = Star.query.all()
        personas = Persona.query.all()

        inventory = dict()
        for star in stars:
            inventory[star.id] = {
                "type": "Star",
                "creator": star.creator_id,
                "modified": star.modified
            }

        for persona in personas:
            inventory[persona.id] = {
                "type": "persona",
                "modified": persona.modified
            }

        inventory_json = json.dumps(inventory)
        return inventory_json

    def on_models_committed(self, sender, changes):
        """ Notify all connected peers about modifications to Stars, Personas """
        for model, change in changes:
            # Identify object type
            if isinstance(model, Star):
                object_type = "Star"
            elif isinstance(model, Persona):
                object_type = "Persona"
            else:
                continue

            # Construct message
            message = dict()
            message["message_type"] = "change_notification"
            message["change"] = change
            message["object_type"] = object_type
            message["object_id"] = model.id
            message["change_time"] = model.modified.isoformat()
            message["port"] = PEERMANAGER_PORT
            message_json = json.dumps(message)

            # Queue message once for every online peer
            for address in self.peers:
                self.message_pool.spawn(self.send_message, address, message_json)

    def send_message(self, address, message):
        """ Send a message  """
        from gevent import socket

        # Send message
        sock = socket.socket(type=socket.SOCK_DGRAM)
        sock.connect(address)
        sock.send(message)
        try:
            data, address = sock.recvfrom(8192)
            app.logger.info("[{source}] Replied: {resp}".format(
                source=self.source_format(address), resp=data))
        except Exception, e:
            self.update_peer_list()
            app.logger.error("[{source}] Replied: {error}".format(
                source=self.source_format(address), error=e))

    def update_peer_list(self):
        """ Update peer list from login server """
        # TODO: implement actual server connection
        if SERVER_PORT == 5000:
            self.peers = [("localhost", 5051), ("localhost", 50590)]
        else:
            self.peers = [("localhost", 5050)]

        self.logger.info("Updated peer list ({} online)".format(len(self.peers)))

    def login(self):
        """ Create session at login server """
        pass

    def logout(self):
        """ Destroy session at login server """
        pass

    def keep_alive(self):
        """ Ping server to keep session alive """
        pass

    def register_persona(self):
        """ Register a persona on the login server """
        pass

    def delete_account(self):
        """ Remove a persona from login server, currently not implemented """
        pass

    def shutdown(self):
        self.pool.kill()
        self.logout()


if __name__ == '__main__':
    init_db()
    if USE_DEBUG_SERVER:
        # flask development server
        app.run(SERVER_HOST, SERVER_PORT)
    else:
        # datagram server
        peermanager = PeerManager('{}:{}'.format(SERVER_HOST, PEERMANAGER_PORT))
        peermanager.start()
        # gevent server
        local_server = WSGIServer(('', SERVER_PORT), app)
        local_server.serve_forever()
