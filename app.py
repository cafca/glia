import sqlite3
from flask import Flask, request, g, redirect, render_template, url_for, flash
from flask.ext.wtf import Form, TextField, Required, Email
from gevent.wsgi import WSGIServer
from contextlib import closing

""" Config """
DATABASE = '/tmp/khemia.db'
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'default'

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


@app.before_request
def before_request():
    g.db = connect_db()


@app.teardown_request
def teardown_request(exception):
    g.db.close()

""" Views """


@app.route('/')
def universe():
    """ Render the landing page """
    # Redirect to >new persona< if no persona is found
    personas = g.db.execute('SELECT name, email FROM personas').fetchall()
    app.logger.info("Currently {} personas.".format(len(personas)))
    if len(personas) == 0:
        return redirect(url_for('create_persona'))

    return render_template('universe.html', personas=personas)


@app.route('/p/<persona_id>/')
def persona():
    """ Render home of a persona """
    pass


class Create_persona_form(Form):
    """ Generate form for creating a persona """
    name = TextField('Name', validators=[Required(), ])
    email = TextField('Email (optional)', validators=[Email(), ])


@app.route('/p/create', methods=['GET', 'POST'])
def create_persona():
    """ Render page for creating new persona """
    form = Create_persona_form()
    if form.validate_on_submit():
        g.db.execute('INSERT INTO personas (name, email) VALUES (?, ?)',
            [request.form['name'], request.form['email']])
        g.db.commit()
        flash("Persona {} created!".format(request.form['name']))
        return redirect(url_for('universe'))

    return render_template('create_persona.html',
        form=form,
        next=url_for('create_persona'))


if __name__ == '__main__':
    init_db()

    # flask development server
    app.run()

    # gevent server
    #local_server = WSGIServer(('', 12345), app)
    #local_server.serve_forever()
