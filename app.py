import datetime
import gevent
import sys

from flask import abort, Flask, json, request, flash, g, redirect, render_template, url_for, session
from flask.ext.wtf import Form, TextField as WTFTextField, Required, Email
from flask.ext.couchdb import CouchDBManager, DateTimeField, Document, TextField, ViewDefinition, ViewField
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
from gevent.wsgi import WSGIServer
from humanize import naturaltime
from werkzeug.local import LocalProxy
from werkzeug.contrib.cache import SimpleCache

""" Config """
DATABASE = 'khemia.db'
DEBUG = True
SEND_FILE_MAX_AGE_DEFAULT = 1
# TODO: Generate after installation, keep secret.
SECRET_KEY = '\xae\xac\xde\nIH\xe4\xed\xf0\xc1\xb9\xec\x08\xf6uT\xbb\xb6\x8f\x1fOBi\x13'
#pw: jodat
PASSWORD_HASH = '8302a8fbf9f9a6f590d6d435e397044ae4c8fa22fdd82dc023bcc37d63c8018c'
SERVER_NAME = 'app.soma:5000'

app = Flask(__name__)
app.config.from_object(__name__)
app.jinja_env.filters['naturaltime'] = naturaltime


# Setup SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + DATABASE
db = SQLAlchemy(app)


# Setup Document Types
class Persona(db.Model):
    id = db.Column(db.String(32), primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    private = db.Column(db.Text)
    public = db.Column(db.Text)
    starmap = db.relationship('Star', backref=db.backref('creator'))

    def __init__(self, id, username, email, private, public):
        self.id = id
        self.username = username
        self.email = email
        self.private = private
        self.public = public


class Star(db.Model):
    id = db.Column(db.String(32), primary_key=True)
    text = db.Column(db.Text)
    created = db.Column(db.DateTime, default=datetime.datetime.now())
    modified = db.Column(db.DateTime, default=datetime.datetime.now(), onupdate=datetime.datetime.now())
    creator_id = db.Column(db.String(32), db.ForeignKey('persona.id'))

    def __init__(self, id, text, creator):
        self.id = id
        self.text = text
        self.creator_id = creator

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


class Create_star_form(Form):
    """ Generate form for creating a star """
    text = WTFTextField('Content', validators=[Required(), ])


@app.route('/s/create', methods=['GET', 'POST'])
def create_star():
    from uuid import uuid4
    """ Create a new star """

    # TODO: Allow selection of author persona
    if session['active_persona'] == "":
        abort(404)
    creator = session['active_persona']

    form = Create_star_form()
    if form.validate_on_submit():
        app.logger.info('Creating new star')
        uuid = uuid4().hex

        new_star = Star(
            uuid,
            request.form['text'],
            creator)
        db.session.add(new_star)
        db.session.commit()

        flash('New star created!')

        gevent.spawn(starbeam, uuid)
        return redirect(url_for('star', id=uuid))
    return render_template('create_star.html', form=form, creator=creator)


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
            raise ValueError("Not enough layout cells provided for content.")

        class_name = "col{c} row{r} w{width} h{height}".format(
            c=self.layout[self.index][0],
            r=self.layout[self.index][1],
            width=self.layout[self.index][2],
            height=self.layout[self.index][3])

        self.index += 1
        return class_name


class DatagramServer(gevent.server.DatagramServer):
    def handle(self, data, address):
        print "{} got {}".format(address[0], data)
        self.socket.sendto('Received {} bytes'.format(len(data)), address)


def starbeam(star_id):
    from gevent import socket

    with app.app_context():
        star = Star.query.filter_by(id=star_id).first()
        address = ('localhost', 9000)
        message = "Changed star {} at {}".format(star.id, star.modified)
        sock = socket.socket(type=socket.SOCK_DGRAM)
        sock.connect(address)
        print 'Sending %s bytes to %s:%s' % ((len(message), ) + address)
        sock.send(message)
        data, address = sock.recvfrom(8192)
        print '%s:%s: got %r' % (address + (data, ))


if __name__ == '__main__':
    init_db()
    # flask development server
    #app.run()

    # datagram server
    DatagramServer(':9000').start()

    # gevent server
    local_server = WSGIServer(('', 5000), app)
    local_server.serve_forever()
