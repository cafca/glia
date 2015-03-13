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

from nucleus.nucleus.models import Persona, User, Group, PersonaAssociation, Star
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

    star_candidates = group.profile.index.filter(Star.oneup_count>0)
    stars = sorted(star_candidates, key=Star.hot, reverse=True)[:15]

    return render_template('group.html', group=group, stars=stars)


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
        session["active_persona"] = form.user.active_persona.id
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
    session["active_persona"] = None
    app.logger.debug("{} logged out.".format(user))
    return redirect(url_for('.index'))


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Signup a new user"""
    import sendgrid
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

        # Send confirmation email
        sg = sendgrid.SendGridClient('YOUR_SENDGRID_USERNAME', 'YOUR_SENDGRID_PASSWORD')

        message = sendgrid.Mail()
        message.add_to("{} <{}>".format(form.username.data, form.email.data))
        message.set_subject('Please confirm your email address')
        message.set_text(render_template("email/signup_confirmation.html", user=user))
        message.set_from('RKTIK Email Confirmation')
        status, msg = sg.send(message)

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


@login_required
@app.route('/validate', methods=["GET", "POST"])
def signup_validation():
    """Validate a user's email adress"""

    signup_code = request.args.get('signup_code')
    if current_user.active:
        flash("Your account is already activated. You're good to go.")
    if not current_user.valid_signup_code(signup_code):
        app.logger.error("User {} tried validating with invalid signup code {}.".format(current_user, signup_code))
        current_user.send_validation_email()
        flash("Oops! Invalid signup code. We have sent you another confirmation email. Please try clicking the link in that new email. ", "error")
    else:
        app.logger.info("{} activated their account.".format(current_user))
        current_user.active = True
        current_user.signup_code = None
        db.session.add(current_user)
        db.session.commit()
    return redirect('.index')
