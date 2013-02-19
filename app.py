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
    private = db.Column(db.Text)
    public = db.Column(db.Text)
    starmap = db.relationship('Star', backref=db.backref('creator'))
    modified = db.Column(db.DateTime, default=datetime.datetime.now(), onupdate=datetime.datetime.now())

    def __init__(self, id, username, email, private, public):
        self.id = id
        self.username = username
        self.email = email
        self.private = private
        self.public = public

    def get_absolute_url(self):
        return url_for('persona', id=self.id)


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
        pv = Persona('247a1ca474b04a248c751d0eebf9738f', 'cievent', 'nichte@gmail.com',
'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')
        db.session.add(pv)
        paul = Persona('6e345777ca1a49cd8d005ac5e2f37cac', 'paul', 'mail@vincentahrend.com', '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')
        db.session.add(paul)
        db.session.commit()


def get_active_persona():
    """ Return the currently active persona or 0 if there is no controlled persona. """

    if 'active persona' not in session or session['active_persona'] is None:
        controlled_personas = Persona.query.filter('private != ""')

        if controlled_personas.first() == None:
            return ""
        else:
            session['active_persona'] = controlled_personas.first().id

    return session['active_persona']


def logged_in():
    return cache.get('password') is not None


@app.context_processor
def persona_context():
    return dict(controlled_personas=Persona.query.filter('private != ""'))


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


def encrypt_symmetric(data, password):
    """ Encrypt data using AES algorithm """

    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    from Padding import appendPadding as append_padding

    iv = get_random_bytes(16)
    if password is None:
        app.logger.error("Not logged in")
        abort(500)
    encoder = AES.new(password, AES.MODE_CBC, iv)
    data = append_padding(data)

    # 16 byte IV is prepended to the encrypted data
    return "".join([iv, encoder.encrypt(data)])


def decrypt_symmetric(data, password):
    """ Decrypt data using AES algorithm """

    from Crypto.Cipher import AES
    from Padding import removePadding as remove_padding

    iv = data[:16]
    decoder = AES.new(password, AES.MODE_CBC, iv)
    data = decoder.decrypt(data[16:])

    return remove_padding(data)


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

        # This is the RSA key used to sign the new persona's actions
        key = RSA.generate(2048)

        # Encrypt private key before saving to DB/disk
        key_private = encrypt_symmetric(key.exportKey(), cache.get('password'))
        key_public = encrypt_symmetric(key.publickey().exportKey(), cache.get('password'))

        # Save persona to DB
        p = Persona(
            uuid,
            request.form['name'],
            request.form['email'],
            private=b64encode(key_private),
            public=b64encode(key_public))
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

    # TODO: Allow selection of author persona
    if session['active_persona'] == "":
        # TODO error message
        app.logger.error("No active persona")
        abort(404)
    controlled_personas = Persona.query.filter(Persona.private != None).all()
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


class PeerManager(gevent.server.DatagramServer):
    """ Handle connections to peers """

    def __init__(self, address):
        gevent.server.DatagramServer.__init__(self, address)
        self.logger = app.logger
        self.update_peer_list()
        self.message_pool = Pool(10)

        # Subscribe to database modifications
        models_committed.connect(self.on_models_committed)

    def handle(self, data, address):
        """ Handle incoming messages """
        if len(data) == 0:
            self.logger.info("[{}] Empty message received".format(address[0]))
        else:
            # print "{} got {}".format(address[0], data)
            self.socket.sendto('Received {} bytes'.format(len(data)), address)

            # TODO: Check authenticy of message
            # TODO: Attempt correcting time of message by comparing machine clocks in the message

            # Try parsing the message
            try:
                message = json.loads(data)
            except ValueError, e:
                app.logger.error("[{}] {}".format(address[0], e))
                return

            # Pass on the message depending on message type
            # Currently used message types are:
            # - change_notification
            # - inventory_request
            # - inventory

            # Address of peermanager on the other end
            source_address = (address[0], message["port"])

            if message["message_type"] == "change_notification":
                self.handle_change_notification(message, source_address)
            if message["message_type"] == "download_request":
                self.upload_object(message, source_address)
            if message["message_type"] == "requested_object":
                self.handle_download_received(message, source_address)
            if message["message_type"] == "inventory_request":
                self.handle_inventory_request(message, source_address)
            if message["message_type"] == "inventory":
                self.handle_inventory_received(message, source_address)

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
            o = Star.query.filter_by(id=object_id).first()
        elif object_type == "Persona":
            o = Persona.query.filter_by(id=object_id).first()

        # Reflect changes if neccessary
        if change == "delete":
            if o is None:
                app.logger.info("[{}] {} {} deleted (no local copy)".format(address, object_type, object_id))
            else:
                db.session.delete(o)
                db.session.commit()
                app.logger.info("[{}] {} {} deleted".format(address, object_type, object_id))

        elif change == "insert" and o is None:
            app.logger.info("[{}] New {} {} created".format(address, object_type, object_id))
            # TODO: Check if we even want to have this thing, also below in update
            self.download_object(object_type, object_id, address)

        elif change == "update":
            app.logger.info("[{}] {} {} updated".format(address, object_type, object_id))
            if o is None:
                self.download_object(object_type, object_id, address)
            else:
                # Check if this is a newer version
                if o.modified < change_time:
                    self.download_object(object_type, object_id, address)

            self.logger.info("[{}] {} {} {} at {}".format(
                address[0], message["object_type"], message["object_id"], message["change"], message["time"]))

    def handle_inventory_request(self, message, address):
        """ Send an inventory to the given address """
        pass

    def handle_inventory_received(self, message, address):
        """ Look through an inventory to see if we want to download some of it """
        pass

    def download_object(self, object_type, object_id, source_address):
        """ Request an object from a peer """
        from gevent import socket

        app.logger.info("Requesting object {} from {}".format(object_id, source_address))

        # Construct request
        message = dict()
        message["message_type"] = "download_request"
        message["object_type"] = object_type
        message["object_id"] = object_id
        message["port"] = PEERMANAGER_PORT
        message_json = json.dumps(message)

        # Send request
        sock = socket.socket(type=socket.SOCK_DGRAM)
        sock.connect(source_address)
        sock.send(message_json)

    def upload_object(self, message, address):
        """ Serve an object to address in response to a request """
        from gevent import socket

        # Validate request
        object_type = message["object_type"]
        object_id = message["object_id"]

        # Load object
        if object_type == "Star":
            obj = Star.query.filter_by(id=object_id).first()
        elif object_type == "Persona":
            obj = Persona.query.filter_by(id=object_id).first()

        if obj is None:
            self.socket.sendto(str(), address)
            return

        # Construct response
        message = dict()
        message["port"] = PEERMANAGER_PORT
        message["message_type"] = "requested_object"
        message["object_data"] = obj.json(exclude=["private"])
        message["object_type"] = object_type
        message_json = json.dumps(message)

        # Send response
        sock = socket.socket(type=socket.SOCK_DGRAM)
        sock.connect(address)
        sock.send(message_json)
        app.logger.info("Sent {} {} to {} ({} bytes)".format(object_type, object_id, address, len(message_json)))

    def handle_download_received(self, message, address):
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
            o = Persona(obj["id"], obj["username"], obj["email"], None, obj["public"])
        db.session.add(o)
        db.session.commit()
        app.logger.info("[{}] Added new {} {}".format(address, object_type, obj['id']))

    def update_peer_list(self):
        """ Update peer list from login server """
        # TODO: implement actual server connection
        if SERVER_PORT == 5000:
            self.peers = [("localhost", 5051), ("localhost", 50590)]
        else:
            self.peers = [("localhost", 5050)]

        self.logger.info("Updated peer list ({} online)".format(len(self.peers)))

    def on_models_committed(self, sender, changes):
        """ Notify all connected peers about modifications to Stars, Personas """
        #with app.app_context():
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
            for peer in self.peers:
                gevent.spawn(self.queue_message, peer, message_json)

    def queue_message(self, peer, message):
        """ Add a message greenlet once a pool slot is available """
        if self.message_pool.full():
            self.message_pool.wait_available()
        self.message_pool.spawn(self.send_message, peer, message)

    def send_message(self, peer, message):
        """ Send a message  """
        from gevent import socket

        # Send message
        sock = socket.socket(type=socket.SOCK_DGRAM)
        sock.connect(peer)
        sock.send(message)
        try:
            data, address = sock.recvfrom(8192)
            app.logger.info("[{}] {}".format(address[0], data))
        except Exception, e:
            self.update_peer_list()
            app.logger.error("[{}] {}".format(peer, e))

    def inventory(self):
        """ Return inventory of all data stored on this machine in json format """
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
