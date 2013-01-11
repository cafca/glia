import datetime

from flask import abort, Flask, request, flash, g, redirect, render_template, url_for, session
from flask.ext.wtf import Form, TextField as WTFTextField, Required, Email
from flask.ext.couchdb import CouchDBManager, DateTimeField, Document, TextField, ViewDefinition, ViewField
#from gevent.wsgi import WSGIServer
from humanize import naturaltime
from werkzeug.local import LocalProxy
from werkzeug.contrib.cache import SimpleCache

""" Config """
DEBUG = True
SEND_FILE_MAX_AGE_DEFAULT = 1
# TODO: Generate after installation, keep secret.
SECRET_KEY = '\xae\xac\xde\nIH\xe4\xed\xf0\xc1\xb9\xec\x08\xf6uT\xbb\xb6\x8f\x1fOBi\x13'
#pw: jodat
PASSWORD_HASH = '8302a8fbf9f9a6f590d6d435e397044ae4c8fa22fdd82dc023bcc37d63c8018c'
SERVER_NAME = 'app.soma:5000'

COUCHDB_SERVER = 'http://app.soma:5984'
COUCHDB_DATABASE = 'ark'

app = Flask(__name__)
app.config.from_object(__name__)
app.jinja_env.filters['naturaltime'] = naturaltime


# Setup CouchDB
manager = CouchDBManager()

# Setup SQLAlchemy
#app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/test.db"
#db = SQLAlchemy(app)


# Setup Document Types
class Persona(Document):
    doc_type = "persona"

    username = TextField()
    email = TextField()
    private = TextField()
    public = TextField()
    created = DateTimeField(default=datetime.datetime.now)


class Star(Document):
    doc_type = 'star'

    text = TextField()
    creator_id = TextField()
    creator_name = TextField()
    created = DateTimeField(default=datetime.datetime.now)

    by_date = ViewField('soma', '''\
    function (doc) {
        if (doc.doc_type == 'star') {
            emit(doc.created, doc);
        }
    }''')

    by_creator = ViewField('soma', '''\
    function (doc) {
        if (doc.doc_type == 'star') {
            emit(doc.creator_id, doc);
        }
    }
    ''')
manager.add_viewdef([Star.by_date, Star.by_creator])


# Setup View Definitions
controlled_personas_view = ViewDefinition('soma', 'controlled_personas', '''\
        function (doc) {
            if (doc.doc_type == 'persona' && doc.private != "") {
                emit(doc.username, doc);
            }
        }
    ''')
manager.add_viewdef(controlled_personas_view)

manager.setup(app)

# Allows access of 'g.couch' through 'couch'
couch = LocalProxy(lambda: g.couch)

# Setup Cache
cache = SimpleCache()


""" DB code """


def get_active_persona():
    """ Return the currently active persona or 0 if there is no controlled persona. """

    if 'active persona' not in session or session['active_persona'] is None:
        controlled_personas = controlled_personas_view()

        if len(controlled_personas) == 0:
            return False
        else:
            session['active_persona'] = controlled_personas.rows[0].value['_id']

    return session['active_persona']


def logged_in():
    return cache.get('password') is not None


@app.context_processor
def persona_context():
    return dict(controlled_personas=controlled_personas_view().rows)


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

    #if request.base_url not in [setup_url, login_url] and not logged_in():
    #    app.logger.info("Redirecting to Login")
    #    return redirect(url_for('login', _external=True))


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

    persona = Persona.load(id)
    if persona is None:
        abort(404)

    stars = Star.by_creator()[id].rows[:4]

    starmap = list()
    for star in stars[:5]:
        starmap.append({
            "id": star.id,
            "created": star.created,
            "title": star.title if "title" in star else None,
            "text": [star.text, ],
            "creator": {
                "id": star.creator_id,
                "name": star.creator_name}
        })

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
                id=uuid,
                active=False,
                username=request.form['name'],
                email=request.form['email'],
                private=b64encode(key_private),
                public=b64encode(key_public))
        p.store()

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
    if session['active_persona'] == '0':
        abort(404)
    creator = Persona.load(session['active_persona'])

    form = Create_star_form()
    if form.validate_on_submit():
        app.logger.info('Creating new star')
        uuid = uuid4().hex

        new_star = Star(
            id=uuid,
            text=request.form['text'],
            creator_id=creator.id,
            creator_name=creator.username)
        new_star.store()

        flash('New star created!')
        return redirect(url_for('star', id=uuid))
    return render_template('create_star.html', form=form, creator=creator)


@app.route('/')
def universe():
    """ Render the landing page """

    stars = Star.by_date().rows

    constellation = list()
    for star in stars[:4]:
        constellation.append({
            "id": star.id,
            "created": star.created,
            "title": star.title if "title" in star else None,
            "text": [star.text, ],
            "creator": {
                "id": star.creator_id,
                "name": star.creator_name}
        })

    vizier = Vizier([
        [1, 1, 6, 4],
        [1, 5, 4, 2],
        [5, 5, 2, 2],
        [7, 1, 2, 5]
    ])

    return render_template('universe.html', layout="sternenhimmel", constellation=constellation, vizier=vizier)


@app.route('/s/<id>/', methods=['GET'])
def star(id):
    """ Display a single star """
    star = Star.load(id)
    creator = Persona.load(star.creator_id)

    star = {
        "id": star.id,
        "title": star.title if "title" in star else None,
        "text": [star.text, ] if "text" in star else None,
        "created": star.created,
        "creator": {
            "id": star.creator_id,
            "name": star.creator_name
        }}

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


if __name__ == '__main__':
    # flask development server
    app.run()

    # gevent server
    #local_server = WSGIServer(('', 12345), app)
    #local_server.serve_forever()
