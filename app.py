import sqlite3
from flask import abort, Flask, request, flash, g, redirect, render_template, url_for, session
from flask.ext.wtf import Form, TextField, Required, Email
from gevent.wsgi import WSGIServer
from contextlib import closing

""" Config """
DATABASE = '/tmp/khemia.db'
DEBUG = True
# TODO: Generate after installation, keep secret.
SECRET_KEY = '\xae\xac\xde\nIH\xe4\xed\xf0\xc1\xb9\xec\x08\xf6uT\xbb\xb6\x8f\x1fOBi\x13'
PASSWORD_HASH = None

app = Flask(__name__)
app.config.from_object(__name__)

""" DB code """


def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql') as f:
            db.cursor().executescript(f.read())
        db.commit()

def get_active_persona():
    """ Return the currently active persona or 0 if there is no controlled persona. """
    controlled_personas = g.db.execute(
        "SELECT id, active FROM personas WHERE private is not null ORDER BY active DESC").fetchall()
    if len(controlled_personas) == 0:        
        return "0"
    else:
        # Personas are ordered by active-ness so the first attr of the first persona
        # is the active persona's ID (controlled_personas[0][0])
        if controlled_personas[0][0] != "1":
            g.db.execute("UPDATE personas SET active=1 WHERE id=?", [controlled_personas[0][0],])
            g.db.commit()
        return controlled_personas[0][0]


@app.before_request
def before_request():
    g.db = connect_db()
    session['active_persona'] = get_active_persona()
    if app.config['PASSWORD_HASH'] == None and request.base_url != 'http://localhost:5000/setup':
        return redirect(url_for('setup'))
    if request.base_url != 'http://localhost:5000/login' and not session.get('logged_in'):
        return redirect(url_for('login'))


@app.teardown_request
def teardown_request(exception):
    g.db.close()

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
        session['password'] = pw_submitted

        if sha256(pw_submitted) != app.config['PASSWORD_HASH']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            flash('You are now logged in')
            return redirect(url_for('universe'))
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('password', None)
    flash('You were logged out')
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    from Crypto.Protocol.KDF import PBKDF2
    from hashlib import sha256

    error = None
    if request.method == 'POST':
        if request.form['password'] is None:
            error = 'Please enter a password'
        else:
            salt = app.config['SECRET_KEY']
            password = PBKDF2(request.form['password'], salt)
            app.config['PASSWORD_HASH'] = sha256(password)
            session['logged_in'] = True
            return redirect(url_for('create_persona'))
    return render_template('setup.html', error=error)


@app.route('/')
def universe():
    """ Render the landing page """
    # Redirect to >new persona< if no persona is found
    personas = g.db.execute('SELECT * FROM personas').fetchall()
    if session['active_persona'] == '0':
        return redirect(url_for('create_persona'))

    return render_template('universe.html', personas=personas)


@app.route('/p/<id>/')
def persona(id):
    """ Render home of a persona """
    persona = g.db.execute("SELECT id,name,email FROM personas WHERE id=?",
        [id,]).fetchone()
    if persona is None:
        abort(404)

    starmap = g.db.execute("SELECT id,text FROM stars WHERE creator=?",
        [id, ]).fetchall()

    return render_template('persona.html', persona=persona, starmap=starmap)


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
        # TODO: replace password from app config with something else
        key_private = encrypt_symmetric(key.exportKey(), session['password'])
        key_public = encrypt_symmetric(key.publickey().exportKey(), session['password'])

        g.db.execute('INSERT INTO personas (id, name, email, private, public) VALUES (?, ?, ?, ?, ?)',
            [uuid,
            request.form['name'], 
            request.form['email'], 
            b64encode(key_private), 
            b64encode(key_public)])
        g.db.commit()

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
    init_db()

    # flask development server
    app.run()

    # gevent server
    #local_server = WSGIServer(('', 12345), app)
    #local_server.serve_forever()
