import sqlite3
from flask import abort, Flask, request, flash, g, redirect, render_template, url_for, session
from flask.ext.wtf import Form, TextField, Required, Email
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
from gevent.wsgi import WSGIServer
from contextlib import closing

""" Config """
DATABASE = '/tmp/khemia.db'
DEBUG = True
# TODO: Generate after installation, keep secret.
SECRET_KEY = '\xae\xac\xde\nIH\xe4\xed\xf0\xc1\xb9\xec\x08\xf6uT\xbb\xb6\x8f\x1fOBi\x13'
PASSWORD_HASH = None
SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/khemia.db'
SERVER_NAME = 'app.soma:5000'

app = Flask(__name__)
app.config.from_object(__name__)
db = SQLAlchemy(app)


""" DB code """


def init_db():
    try:
        Persona.query.first()
    except OperationalError:
        db.create_all()
        pv = Persona('247a1ca474b04a248c751d0eebf9738f', True, 'cievent', 'nichte@gmail.com',
'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')
        db.session.add(pv)
        db.session.commit()


def get_active_persona():
    """ Return the currently active persona or 0 if there is no controlled persona. """
    controlled_personas = Persona.query.filter('private != ""')

    if controlled_personas.first() == None:
        return "0"
    else:
        active = controlled_personas.filter_by(active=True).first()
        if active:
            return active
        else:
            active = controlled_personas.first()
            active.active = True
            return active


def logged_in():
    if hasattr(g, 'password'):
        if g.password is not None:
            return True
    return False


@app.before_request
def before_request():
    # TODO: serve favicon.ico
    if request.base_url[-3:] == "ico":
        abort(404)

    setup_url = "/".join(["http:/", app.config['SERVER_NAME'], "setup"])
    login_url = "/".join(["http:/", app.config['SERVER_NAME'], "login"])

    session['active_persona'] = get_active_persona()

    if app.config['PASSWORD_HASH'] == None and request.base_url != setup_url:
        return redirect(url_for('setup', _external=True))

    if request.base_url not in [setup_url, login_url] and logged_in():
        return redirect(url_for('login', _external=True))


@app.teardown_request
def teardown_request(exception):
    pass

""" Models """


class Persona(db.Model):
    id = db.Column(db.String(32), primary_key=True)
    active = db.Column(db.Boolean, default=False)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    private = db.Column(db.Text)
    public = db.Column(db.Text)

    def __init__(self, id, active, username, email, private, public):
        self.id = id
        self.active = active
        self.username = username
        self.email = email
        self.private = private
        self.public = public

    def __repr__(self):
        return '<Persona {!r}>'.format(self.username)


class Star(db.Model):
    id = db.Column(db.String(32), primary_key=True)
    text = db.Column(db.Text)
    creator_id = db.Column(db.String(32), db.ForeignKey('persona.id'))
    creator = db.relationship('Persona', backref=db.backref('starmap', lazy='dynamic'))

    def __init__(self, id, text, creator):
        self.id = id
        self.text = text
        self.creator = creator

    def __repr__(self):
        return '<Star {!r}:{!r}>'.format(self.creator.username, self.text)


""" Views """


@app.route('/login', methods=['GET', 'POST'])
def login():
    from Crypto.Protocol.KDF import PBKDF2
    from hashlib import sha256

    error = None
    if request.method == 'POST':
        # TODO: Is this a good idea?
        salt = app.config['SECRET_KEY']
        pw_submitted = PBKDF2(request.form['password'], salt)

        if sha256(pw_submitted) != app.config['PASSWORD_HASH']:
            error = 'Invalid password'
        else:
            session['password'] = pw_submitted
            session['logged_in'] = True
            g.password = pw_submitted
            flash('You are now logged in')
            return redirect(url_for('universe'))
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('password', None)
    g.password = None
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
            app.config['PASSWORD_HASH'] = sha256(password)
            session['logged_in'] = True
            g.password = password
            return redirect(url_for('create_persona'))
    return render_template('setup.html', error=error)


@app.route('/')
def universe():
    """ Render the landing page """
    # Redirect to >new persona< if no persona is found
    personas = Persona.query.all()
    if session['active_persona'] == '0':
        return redirect(url_for('create_persona'))

    return render_template('universe.html', personas=personas)


@app.route('/p/<id>/')
def persona(id):
    """ Render home of a persona """
    persona = Persona.query.filter_by(id=id).first_or_404()

    return render_template('persona.html', persona=persona)


class Create_persona_form(Form):
    """ Generate form for creating a persona """
    name = TextField('Name', validators=[Required(), ])
    email = TextField('Email (optional)', validators=[Email(), ])


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
        key_private = encrypt_symmetric(key.exportKey(), session['password'])
        key_public = encrypt_symmetric(key.publickey().exportKey(), session['password'])

        # Save persona to DB
        p = Persona(uuid, False, request.form['name'], request.form['email'], b64encode(key_private), b64encode(key_public))
        db.session.add(p)
        db.session.commit()

        flash("New persona {} created!".format(request.form['name']))
        return redirect(url_for('persona', id=uuid))

    return render_template('create_persona.html',
        form=form,
        next=url_for('create_persona'))


class Create_star_form(Form):
    """ Generate form for creating a star """
    text = TextField('Content', validators=[Required(), ])


@app.route('/s/create', methods=['GET', 'POST'])
def create_star():
    from uuid import uuid4
    """ Create a new star """

    creator = g.db.execute("SELECT name FROM personas WHERE id=?",
        [session['active_persona']]).fetchone()

    form = Create_star_form()
    if form.validate_on_submit():
        uuid = uuid4().hex

        g.db.execute("INSERT INTO stars (id, creator, text) VALUES (?, ?, ?)",
            [uuid, session['active_persona'], request.form['text']])
        g.db.commit()

        flash('New star created!')
        return redirect(url_for('star', id=uuid))
    return render_template('create_star.html', form=form, creator=creator)


@app.route('/s/<id>/', methods=['GET'])
def star(id):
    """ Display a single star """
    star = g.db.execute("SELECT id,creator,text FROM stars WHERE id=?",
        [id, ]).fetchone()
    if star is None:
        abort(404)
    creator = g.db.execute("SELECT id,name FROM personas WHERE id=?",
        [star[1], ]).fetchone()

    return render_template('star.html', star=star, creator=creator)


if __name__ == '__main__':

    # flask development server
    init_db()
    app.run()

    # gevent server
    #local_server = WSGIServer(('', 12345), app)
    #local_server.serve_forever()
