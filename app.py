#!/usr/bin/python

import gevent
import datetime
import sys
import umemcache
import requests

from analytics import score, epoch_seconds
from blinker import Namespace
from dateutil.parser import parse as dateutil_parse
from flask import abort, Flask, json, request, flash, g, redirect, render_template, url_for, session
from flask.ext.wtf import Form, TextField as WTFTextField, SelectField as WTFSelectField, Required, Email
from flask.ext.sqlalchemy import SQLAlchemy
from gevent import Greenlet
from gevent.wsgi import WSGIServer
from gevent.pool import Pool
from humanize import naturaltime
from keyczar.keys import RsaPrivateKey, RsaPublicKey
from set_hosts import test_host_entry
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

LOGIN_SERVER_HOST = "app.soma"
LOGIN_SERVER_PORT = "24500"
LOGIN_SERVER = "{}:{}".format(LOGIN_SERVER_HOST, LOGIN_SERVER_PORT)

app = Flask(__name__)
app.config.from_object(__name__)
app.jinja_env.filters['naturaltime'] = naturaltime


# Setup SQLAlchemy
DATABASE = 'khemia_{}.db'.format(SERVER_PORT)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + DATABASE
db = SQLAlchemy(app)

# Create blinker signal namespace
notification_signals = Namespace()
star_created = notification_signals.signal('star-created')
star_deleted = notification_signals.signal('star-deleted')
persona_created = notification_signals.signal('persona-created')


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


# Setup Document Types
class Persona(Serializable, db.Model):
    id = db.Column(db.String(32), primary_key=True)
    username = db.Column(db.String(80))
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

    def __str__(self):
        return "{} <{}>".format(self.username, self.id)

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
        from base64 import b64encode

        key_private = RsaPrivateKey.Read(self.sign_private)
        signature = key_private.Sign(data)
        return b64encode(signature)

    def verify(self, data, signature_b64):
        """ Verify a signature using RSA """
        from base64 import b64decode

        signature = b64decode(signature_b64)
        key_public = RsaPublicKey.Read(self.sign_public)
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

    def __str__(self):
        return "<Star {}-{}>".format(self.creator_id, self.created)

    def get_absolute_url(self):
        return url_for('star', id=self.id)

    def hot(self):
        """i reddit"""
        from math import log
        #s = score(self)
        s = 1.0
        order = log(max(abs(s), 1), 10)
        sign = 1 if s > 0 else -1 if s < 0 else 0
        return round(order + sign * epoch_seconds(self.created) / 45000, 7)


# Setup Cache
cache = SimpleCache()


""" DB code """


def init_db():
    try:
        Persona.query.first()
    except OperationalError:
        app.logger.info("Initializing DB")
        db.create_all()

        """# Generate test persona #1
        pv = Persona('247a1ca474b04a248c751d0eebf9738f', 'cievent', 'nichte@gmail.com')
        pv.generate_keys('jodat')
        db.session.add(pv)

        # Generate test persona #2
        paul = Persona('6e345777ca1a49cd8d005ac5e2f37cac', 'paul', 'mail@vincentahrend.com')
        paul.generate_keys('jodat')
        db.session.add(paul)

        db.session.commit()"""


def get_active_persona():
    """ Return the currently active persona or 0 if there is no controlled persona. """

    if 'active_persona' not in session or session['active_persona'] is None:
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

        # TODO: Error message when user already exists
        db.session.add(p)
        db.session.commit()

        # Distribute "birth" certificate
        data = dict({
            "object_type": "Persona",
            "object_id": uuid,
            "change": "insert",
            "change_time": p.modified.isoformat()
        })

        message = Message(message_type="change_notification", data=data)
        persona_created.send(create_persona, message=message)

        flash("New persona {} created!".format(p.username))
        return redirect(url_for('persona', id=uuid))

    return render_template('create_persona.html',
        form=form,
        next=url_for('create_persona'))


@app.route('/p/<id>/activate', methods=['GET'])
def activate_persona(id):
    """ Activate a persona """
    p = Persona.query.get(id)
    if not p:
        app.logger.error("Tried to activate a nonexistent persona")
        abort(404)
    if p.sign_private == "":
        app.logger.error("Tried to activate foreign persona")
        flash("That is not you!")
    else:
        app.logger.info("Activated persona {}".format(id))
        session['active_persona'] = id
    return redirect(url_for('universe'))


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

    # Load author drop down contents
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

        # Create certificate
        data = dict({
            "object_type": "Star",
            "object_id": uuid,
            "change": "insert",
            "change_time": new_star.modified.isoformat()
        })

        message = Message(message_type="change_notification", data=data)
        message.sign(new_star.creator)
        star_created.send(create_star, message=message)

        return redirect(url_for('star', id=uuid))
    return render_template('create_star.html', form=form, controlled_personas=controlled_personas)


@app.route('/s/<id>/delete', methods=["GET"])
def delete_star(id):
    """ Delete a star """
    # TODO: Should only accept POST instead of GET
    # TODO: Check permissions

    # Load instance and creator persona
    s = Star.query.get(id)

    if s is None:
        abort(404)

    # Create deletion request
    data = dict({
        "object_type": "Star",
        "object_id": s.id,
        "change": "delete",
        "change_time": datetime.datetime.now().isoformat()
    })

    message = Message(message_type="change_notification", data=json.dumps(data))
    message.sign(s.creator)

    # Delete instance from db
    db.session.delete(s)
    db.session.commit()

    # Distribute deletion request
    star_deleted.send(delete_star, message=message)

    app.logger.info("Deleted star {}".format(id))

    return redirect(url_for('debug'))


@app.route('/')
def universe():
    """ Render the landing page """
    from analytics import PageManager
    stars = Star.query.all()
    pm = PageManager()
    page = pm.auto_layout(stars)

    return render_template('universe.html', layout="sternenhimmel", stars=page)


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
                        app.logger.warning("Double binding of cell ({x},{y})".format(x=col, y=row))
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
    """ Container for peer messages """

    def __init__(self, message_type, data):
        self.message_type = message_type
        self.data = data
        self.timestamp = None
        self.send_attributes = ["message_type", "data"]

    def __str__(self):
        if hasattr(self, "author_id"):
            author = Persona.query.get(self.author_id)
            if author:
                signed = "signed {username}<{id}>".format(
                    username=author.username, id=self.author_id)
            else:
                signed = "signed Anonymous<{id}>".format(id=self.author_id)
        else:
            signed = "unsigned"
        return "Message ({signed})".format(signed=signed)

    def json(self):
        """Return JSON representation"""
        message = dict()
        for attr in self.send_attributes:
            message[attr] = getattr(self, attr)
        message["timestamp"] = datetime.datetime.now().isoformat()
        return json.dumps(message)

    @staticmethod
    def read(data):
        """Create a Message instance from its JSON representation"""

        msg = json.loads(data)
        message = Message(message_type=msg["message_type"], data=msg["data"])

        if "signature" in msg:
            message.signature = msg["signature"]
            message.author_id = msg["author_id"]

            # Verify signature
            p = Persona.query.get(message.author_id)
            if p is None:
                # TODO: Try to retrieve author persona from network
                app.logger.warning("[{msg}] Could not verify signature. Author pubkey missing.".format(msg=message))
            else:
                is_valid = p.verify(message.data, message.signature)
                if not is_valid:
                    app.logger.error("[{msg}] Signature invalid!".format(msg=message))
                    raise ValueError("Invalid signature")

            # data field needs to be decoded if the message is signed
            message.data = json.loads(message.data)
        return message

    def sign(self, author):
        """Sign a message using an author persona. Make sure not to change message data after signing"""

        if not isinstance(self.data, str):
            self.data = json.dumps(self.data)
        self.signature = author.sign(self.data)
        self.author_id = author.id
        self.send_attributes.extend(["signature", "author_id"])


class PeerManager(gevent.server.DatagramServer):
    """ Handle connections to peers """

    def __init__(self, address):
        gevent.server.DatagramServer.__init__(self, address)
        self.logger = app.logger
        self.message_pool = Pool(10)
        self.source_format = lambda address: "{host}:{port}".format(host=address[0], port=address[1])
        self.sessions = dict()
        self.peers = dict()

        # Subscribe notification distribution to signals
        star_created.connect(self.on_notification_signal)
        star_deleted.connect(self.on_notification_signal)
        persona_created.connect(self.on_notification_signal)
        persona_created.connect(self.on_persona_created)

        # Login all personas
        persona_set = Persona.query.filter('sign_private != ""').all()
        for p in persona_set:
            self.message_pool.spawn(self.login, p)

    def request_object(self, object_type, object_id, address):
        """ Request an object from a peer """
        from gevent import socket

        app.logger.info("Requesting {object_type} {object_id} from {source}".format(
            object_type=object_type, object_id=object_id, source=self.source_format(address)))

        # Construct request
        data = {"object_type": object_type, "object_id": object_id}
        message = Message("object_request", data)

        # Send request
        self.send_message(address, message)

    def handle(self, data, address):
        """ Handle incoming messages """
        if len(data) == 0:
            self.logger.info("[{}] Empty message received".format(address[0]))
        else:
            self.logger.debug("[{source}] Received {l} bytes: {json}".format(
                source=self.source_format(address), json=data, l=len(data)))
            self.socket.sendto('Received {} bytes'.format(len(data)), address)

            # TODO: Attempt correcting time of message by comparing machine clocks in the message
            #   (see bittorrent utp spec)

            # Try parsing the message
            try:
                message = Message.read(data)
            except KeyError, e:
                app.logger.error("[{source}] Message malformed ({error})".format(
                    source=self.source_format(address), error=e))
                return

            # Allowed message types
            message_types = [
                "change_notification",
                "object_request",
                "object",
                "inventory_request",
                "inventory"
            ]

            # Identify return path
            try:
                return_address = (address[0], self.peers[address[0]])
            except KeyError, e:
                app.logger.warning("No return path for peer {host}".format(host=address[0]))

            # Pass on the message depending on message type
            if message.message_type in message_types:
                handler = getattr(self, "handle_{message_type}".format(message_type=message.message_type))
                handler(message, return_address)

    def handle_change_notification(self, message, address):
        """ Delete or download the object the notification was about if that is neccessary """

        # Verify message
        # TODO: Check authenticity and authority
        change = message.data["change"]
        object_type = message.data["object_type"]
        object_id = message.data["object_id"]
        change_time = dateutil_parse(message.data["change_time"])

        # Load object if it exists
        if object_type == "Star":
            o = Star.query.get(object_id)
        elif object_type == "Persona":
            o = Persona.query.get(object_id)

        # TODO: Update inventory db

        # Reflect changes if neccessary
        if change == "delete":
            # Check authority to delete
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

            # Request object
            else:
                app.logger.info("[{source}] New {object_type} {object_id} available".format(
                    source=self.source_format(address), object_type=object_type, object_id=object_id))
                # TODO: Check if we even want to have this thing, also below in update
                self.request_object(object_type, object_id, address)

        elif change == "update":

            #
            # WIP & untested
            #

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
        else:
            app.logger.error("[{msg}] Protocol error: Unknown change type '{change}'".format(
                msg=message, change=change))

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
        object_type = message.data["object_type"]
        obj = message.data["object"]

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

        object_id = message.data["object_id"]
        object_type = message.data["object_type"]

        # Load object
        if object_type == "Star":
            obj = Star.query.get(object_id)
        elif object_type == "Persona":
            obj = Persona.query.get(object_id)

        if obj is None:
            # TODO: Serve error message
            app.logger.error("Requested object {type} <{id}> not found".format(
                type=object_type, id=object_id))
            self.socket.sendto(str(), address)
            return

        # Construct response
        data = {
            "object": obj.export(exclude=["sign_private, crypt_private"]),
            "object_type": object_type
        }
        message = Message("object", data)

        # Sign message
        if object_type == "Star" and obj.creator.sign_private != "":
            message.sign(obj.creator)
        elif object_type == "Persona" and obj.sign_private != "":
            message.sign(obj)

        # Send response
        self.send_message(address, message)
        app.logger.info("Sent {object_type} {object_id} to {address}".format(
            object_type=object_type,
            object_id=object_id,
            address=self.source_format(address)
        ))

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

    def on_notification_signal(self, sender, message):
        """ Distribute notification messages """
        app.logger.info("[{sender}] Distributing {msg}".format(sender=sender, msg=message))
        self.distribute_message(message)

    def on_persona_created(self, sender, message):
        """ Register newly created personas with server """
        persona_id = message.data['object_id']
        persona = Persona.query.get(persona_id)
        self.register_persona(persona)

    def distribute_message(self, message):
        """ Distribute a message to all peers who don't already have it """
        if self.peers:
            for host, port in self.peers.iteritems():
                # TODO: Check whether that peer has the message already
                self.message_pool.spawn(self.send_message, (host, port), message)

    def send_message(self, address, message):
        """ Send a message  """
        from gevent import socket

        message_json = message.json()

        # Send message
        sock = socket.socket(type=socket.SOCK_DGRAM)
        sock.connect(address)
        sock.send(message_json)
        try:
            data, address = sock.recvfrom(8192)
            app.logger.info("[{source}] replied: '{resp}'".format(
                source=self.source_format(address), resp=data))
        except Exception, e:
            app.logger.error("[{source}] replied: {error}".format(
                source=self.source_format(address), error=e))

    def server_request(self, url, message=None):
        """ HTTP request to server. Parses response and returns (resp, error_strings). """
        # Make request
        if message:
            headers = {"Content-Type": "application/json"}
            r = requests.post(url, message.json(), headers=headers)
            app.logger.debug("Posted request to server:\n{}".format(r.request.body))
        else:
            r = requests.get(url)
            app.logger.debug("Sent request to server:\n{} {}\n{}".format(
                r.request.method, r.request.url, r.request.body))

        # Parse response
        error_strings = list()

        # Status code above 400 means the request failed
        if r.status_code >= 400:
            error_strings.append("{} (HTTP error)".format(r.status_code))
            return (None, error_strings)

        # Parse JSON, extract errors
        else:
            resp = r.json()
            if 'errors' in resp['data']:
                for error in resp['data']['errors']:
                    error_strings.append("{}: {}".format(error[0], error[1]))
            #app.logger.debug("[server] Received data: {}".format(resp))
            return (resp, error_strings)

    def update_peer_list(self, persona):
        """ Update peer list from login server """
        # TODO: implement actual server connection
        if SERVER_PORT == 5000:
            self.peers = {"127.0.0.1": 5051}
        else:
            self.peers = {"127.0.0.1": 5050}

        peer_list = ['247a1ca474b04a248c751d0eebf9738f', '6e345777ca1a49cd8d005ac5e2f37cac']

        url = "http://{host}/{persona_id}/".format(host=LOGIN_SERVER, persona_id=persona.id)

        self.logger.info("Updated peer list ({} online)".format(len(self.peers)))

    def login(self, persona):
        """ Create session at login server """

        # Check current state
        url = "http://{host}/{persona_id}/".format(host=LOGIN_SERVER, persona_id=persona.id)
        resp, errors = self.server_request(url)

        if errors:
            app.logger.error("Login failed with errors:\n{}".format("\n".join(errors)))
            if not resp:
                return

            # Check error list for code 3 (persona not found) and register new persona if found
            if 3 in [t[0] for t in resp['data']['errors']]:
                self.register_persona(persona)
                return

        # Persona is already logged in
        elif 'session_id' in resp['data']:
            app.logger.info("Persona {} already logged in.".format(persona))
            self.sessions[persona.id] = {
                'session_id': resp['data']['session_id'],
                'timeout': resp['data']['timeout']
            }
            self.queue_keepalive(persona)
            return

        # Do login
        if 'auth' in resp['data']:
            data = {
                'auth_signed': persona.sign(resp['data']['auth'])
            }
            r, errors = self.server_request(url, Message('session', data))

            if errors:
                app.logger.error("Login failed:\n{}".format("\n".join(errors)))
            else:
                self.sessions[persona.id] = {
                    'session_id': r['data']['session_id'],
                    'timeout': r['data']['timeout'],
                }
                app.logger.info("Persona {} logged in until {}".format(
                    persona, dateutil_parse(r['data']['timeout'])))
                self.queue_keepalive(persona)

    def keep_alive(self, persona):
        """ Ping server to keep session alive """

        url = "http://{host}/{persona_id}/".format(host=LOGIN_SERVER, persona_id=persona.id)
        r, errors = self.server_request(url)

        if errors:
            app.logger.error("Error in keep_alive for {}:\n{}".format(
                persona, "\n".join(errors)))

            # Login if session is invalid
            if r and 6 in [t[0] for t in r['data']['errors']]:
                self.login(persona)
        else:
            self.sessions[persona.id] = {
                'session_id': r['data']['session_id'],
                'timeout': r['data']['timeout']
            }
            self.queue_keepalive(persona)

    def queue_keepalive(self, persona):
        """ Send keep-alive some time before the session times out """

        if persona.id not in self.sessions:
            send_in_seconds = 2
        else:
            buf = 30  # seconds
            timeout = dateutil_parse(self.sessions[persona.id]['timeout'])
            send_in_seconds = (timeout - datetime.datetime.now()).seconds - buf
            if send_in_seconds < 0:
                send_in_seconds = 2

        ping = Greenlet(self.keep_alive, persona)
        ping.start_later(send_in_seconds)

    def register_persona(self, persona):
        """ Register a persona on the login server """
        app.logger.info("Registering persona {} with login server".format(persona))

        # Create request
        data = {
            'persona_id': persona.id,
            'email_hashes': None,
            'sign_public': persona.sign_public,
            'crypt_public': persona.crypt_public,
            'reply_to': PEERMANAGER_PORT
        }
        message = Message('create_persona', data)

        url = "http://{host}/{persona}/create".format(host=LOGIN_SERVER, persona=persona.id)
        response, errors = self.server_request(url, message=message)

        if errors:
            app.logger.error("Error creating account on server:\n{}".format("\n".join(errors)))

        # Evaluate response
        if 'session_id' in response['data']:
            app.logger.info("Registered {} with server.".format(persona))
            self.sessions[persona.id] = {
                'session_id': response['data']['session_id'],
                'timeout': response['data']['timeout'],
            }
            self.update_peer_list(persona)
            self.queue_keepalive(persona)

    def delete_account(self):
        """ Remove a persona from login server, currently not implemented """
        pass

    def shutdown(self):
        self.pool.kill()
        self.logout()


if __name__ == '__main__':
    init_db()
    if not test_host_entry:
        app.logger.error("Please execute set_hosts.py with administrator privileges\
            to allow access to Soma at http://app.soma/.")
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
