from flask import Flask, redirect, render_template, url_for
from flask.ext.wtf import Form, TextField, Required, Email
from gevent.wsgi import WSGIServer

app = Flask(__name__)


@app.route('/')
def universe():
    """ Render the landing page """
    # Redirect to >new persona< if no persona is found
    if True:
        return redirect(url_for('create_persona'))

    return render_template('universe.html')


@app.route('/p/<persona_id>/')
def persona():
    """ Render home of a persona """
    pass


class Create_persona_form(Form):
    """ Generate form for creating a persona """
    name = TextField('Name', validators=[Required(), ])
    email = TextField('Email (optional)', validators=[Email(), ])


@app.route('/p/create')
def create_persona():
    """ Render page for creating new persona """
    form = Create_persona_form(csrf_enabled=False)
    return render_template('create_persona.html', form=form)


if __name__ == '__main__':
    app.debug = True
    local_server = WSGIServer(('', 12345), app)
    local_server.serve_forever()
