# -*- coding: utf-8 -*-
"""
    glia.views
    ~~~~~

    Implements public Glia API.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import datetime

from . import app
from .. import db
from flask import request, redirect, render_template, flash, url_for, session
from flask.ext.login import login_user, logout_user, login_required, current_user
from uuid import uuid4

from glia.models import Persona, User, Group, Association
from forms import LoginForm, SignupForm, CreateGroupForm


@login_required
@app.route('/', methods=["GET"])
def index():
    """Front page"""
    groupform = CreateGroupForm()
    groups = Group.query.all()

    return render_template('index.html', groupform=groupform, groups=groups)


@login_required
@app.route('/groups/', methods=["GET", "POST"])
def groups():
    """Create groups"""
    form = CreateGroupForm()

    # Create a group
    if form.validate_on_submit():
        group_id = uuid4().hex
        group = Group(
            id=group_id,
            username=form.name.data,
            admin=current_user.active_persona)
        db.session.add(group)
        db.session.commit()
        flash("Your new group is ready!")
        return redirect(url_for('.group', id=group_id))

    return render_template("groups.html", form=form)


@login_required
@app.route('/groups/<id>', methods=["GET"])
def group(id):
    """Display a group's profile"""
    group = Group.query.get(id)
    if not group:
        flash("Group not found")
        return(redirect(url_for('.groups')))

    session['name'] = current_user.active_persona.username
    session['room'] = group.username

    return render_template('group.html', group=group)


@app.route('/stars/', methods=["POST"])
def create_star():
    """Post a new Star"""
    pass


@app.route('/login', methods=["GET", "POST"])
def login():
    """Login a user"""
    form = LoginForm()
    if form.validate_on_submit():
        app.logger.debug("Form validated fine")
        form.user.authenticated = True
        db.session.add(form.user)
        db.session.commit()
        login_user(form.user, remember=True)
        flash("Welcome back, {}".format(form.user.active_persona.username))
        return form.redirect(url_for('.index'))
    elif request.method == "POST":
        app.logger.error("Invalid password")
        form.password.errors.append("Invalid password.")
    return render_template('login.html', form=form)


@login_required
@app.route('/logout', methods=["GET", "POST"])
def logout():
    """Logout a user"""
    user = current_user
    user.authenticated = False
    db.session.add(user)
    db.session.commit()
    logout_user()
    return redirect(url_for('.index'))


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Signup a new user"""
    from uuid import uuid4
    form = SignupForm()

    if form.validate_on_submit():
        created_dt = datetime.datetime.utcnow()
        user = User(
            email=form.email.data,
            created=created_dt,
            modified=created_dt)
        user.set_password(form.password.data)
        db.session.add(user)

        created_dt = datetime.datetime.utcnow()
        persona = Persona(
            id=uuid4().hex,
            username=form.username.data,
            created=created_dt,
            modified=created_dt)

        db.session.add(persona)

        ap = user.active_persona
        if ap:
            ap.association[0].active = False

        association = Association(user=user, persona=persona, active=True)
        db.session.add(association)
        db.session.commit()

        login_user(user, remember=True)

        flash("Hello {}, you now have your own RKTIK account!".format(form.username.data))

        return form.redirect(url_for('.index'))
    return render_template('signup.html', form=form)
