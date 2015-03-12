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
from functools import wraps
from flask import request, redirect, render_template, flash, url_for, session, current_app
from flask.ext.login import login_user, logout_user, current_user, login_required
from uuid import uuid4
from sqlalchemy.exc import IntegrityError

from nucleus.nucleus.models import Persona, User, Group, PersonaAssociation
from forms import LoginForm, SignupForm, CreateGroupForm


@app.route('/', methods=["GET"])
@login_required
def index():
    """Front page"""
    groupform = CreateGroupForm()
    groups = Group.query.all()

    return render_template('index.html', groupform=groupform, groups=groups)


@app.route('/groups/', methods=["GET", "POST"])
@login_required
def groups():
    """Create groups"""
    form = CreateGroupForm()

    # Create a group
    if form.validate_on_submit():
        group_id = uuid4().hex
        group_created = datetime.datetime.utcnow()
        group = Group(
            id=group_id,
            username=form.name.data,
            admin=current_user.active_persona,
            created=group_created,
            modified=group_created)
        db.session.add(group)
        db.session.commit()
        flash("Your new group is ready!")
        app.logger.debug("{} created new group {}".format(current_user.active_persona, group))
        return redirect(url_for('.group', id=group_id))

    return render_template("groups.html", form=form)


@app.route('/groups/<id>', methods=["GET"])
@login_required
def group(id):
    """Display a group's profile"""
    group = Group.query.get(id)
    if not group:
        flash("Group not found")
        app.logger.warning("Group '{}' not found. User: {}".format(id, current_user))
        return(redirect(url_for('.groups')))

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
        form.user.authenticated = True
        db.session.add(form.user)
        db.session.commit()
        login_user(form.user, remember=True)
        flash("Welcome back, {}".format(form.user.active_persona.username))
        app.logger.debug("User {} logged in with {}.".format(current_user, current_user.active_persona))
        return form.redirect(url_for('.index'))
    elif request.method == "POST":
        app.logger.error("Invalid password for email '{}'".format(form.email.data))
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
    app.logger.debug("{} logged out.".format(user))
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

        # Create keypairs
        app.logger.info("Generating private keys for {}".format(persona))
        persona.generate_keys(form.password.data)

        db.session.add(persona)

        ap = user.active_persona
        if ap:
            ap.association[0].active = False

        association = PersonaAssociation(user=user, persona=persona, active=True)
        db.session.add(association)
        try:
            db.session.commit()
        except IntegrityError, e:
            app.logger.error("Error during signup: {}".format(e))
            db.session.rollback()
            flash("Sorry! There was an error creating your account. Please try again.", "error")
            return render_template('signup.html', form=form)
        else:
            login_user(user, remember=True)

            flash("Hello {}, you now have your own RKTIK account!".format(form.username.data))
            app.logger.debug("Created new account {} with active Persona {}.".format(user, persona))

        return form.redirect(url_for('.index'))
    return render_template('signup.html', form=form)
