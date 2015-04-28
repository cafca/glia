# -*- coding: utf-8 -*-
"""
    glia.views
    ~~~~~

    Implements public Glia API.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import datetime
import traceback

from flask import request, redirect, render_template, flash, url_for, session
from flask.ext.login import login_user, logout_user, current_user, login_required
from forms import LoginForm, SignupForm, CreateGroupForm
from uuid import uuid4
from sqlalchemy.exc import IntegrityError

from . import app
from .. import db
from glia import cache
from glia.web.forms import DeleteStarForm
from glia.web.dev_helpers import http_auth
from glia.web.helpers import send_validation_email
from nucleus.nucleus.models import Persona, User, Group, PersonaAssociation, Star, Starmap, Planet


@app.before_request
def account_notifications():
    if not current_user.is_anonymous and not current_user.is_active:
        flash("Your account is not activated. Please click the link in the email that we sent you.")


@app.route('/debug/')
@http_auth.login_required
def debug():
    """ Display raw data """
    stars = Star.query.all()
    planets = Planet.query.all()
    groups = Group.query.all()
    starmaps = Starmap.query.all()
    users = User.query.all()

    return render_template(
        'debug.html',
        stars=stars,
        users=users,
        planets=planets,
        groups=groups,
        starmaps=starmaps
    )


@app.route('/', methods=["GET"])
@login_required
@http_auth.login_required
def index():
    """Front page"""
    groupform = CreateGroupForm()

    # Collect data for TOC
    groups = Group.query.limit(5)
    group_data = []
    for g in groups:
        g_star_selection = g.profile.index.filter(Star.state >= 0)
        g_top_posts = sorted(g_star_selection, key=Star.hot, reverse=True)[:3]

        group_data.append({
            'group': g,
            'top_posts': g_top_posts
        })

    cache.set('a', 1)
    app.logger.info("Cache: {}".format(cache.get('a')))

    # Collect main page content
    star_selection = Star.query.filter(Star.state >= 0)
    star_selection = sorted(star_selection, key=Star.hot, reverse=True)
    top_posts = []
    while len(top_posts) < min([9, len(star_selection)]):
        candidate = star_selection.pop(0)
        if candidate.oneup_count() > 0:
            top_posts.append(candidate)

    return render_template('index.html', groupform=groupform, group_data=group_data, top_posts=top_posts)


@app.route('/groups/', methods=["GET", "POST"])
@login_required
@http_auth.login_required
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


@app.route('/star/<id>/')
@http_auth.login_required
def star(id=None):
    star = Star.query.get_or_404(id)

    if star.state < 0 and not star.author.controlled():
        flash("This Star is currently unavailable.")
        return(redirect(request.referrer or url_for('.index')))

    return render_template("star.html", star=star)


@app.route('/star/<id>/delete', methods=["GET", "POST"])
@http_auth.login_required
def delete_star(id=None):
    star = Star.query.get_or_404(id)
    form = DeleteStarForm()

    if not star.author.controlled():
        flash("You are not allowed to change {}'s Stars".format(star.author.username))
        app.logger.error("Tried to change visibility of {}'s Stars".format(star.author))
        return redirect(request.referrer or url_for('.index'))

    if form.validate_on_submit():
        if star.state == -2:
            star.set_state(0)
        else:
            star.set_state(-2)

        try:
            db.session.add(star)
            db.session.commit()
        except:
            app.logger.error("Error setting publish state of {}\n{}".format(star, traceback.format_exc()))
            db.session.rollback()
        else:
            flash("Updated visibility of {}".format(star))

            app.logger.info("Star {} set to publish state {}".format(id, star.state))
            return(redirect(url_for(".star", id=star.id)))

    return render_template("delete_star.html", star=star, form=form)


@app.route('/persona/<id>/')
@http_auth.login_required
def persona(id=None):
    pass


@app.route('/groups/<id>', methods=["GET"])
@login_required
@http_auth.login_required
def group(id):
    """Display a group's profile"""
    group = Group.query.get(id)
    if not group:
        flash("Group not found")
        app.logger.warning("Group '{}' not found. User: {}".format(id, current_user))
        return(redirect(url_for('.groups')))

    star_selection = group.profile.index.filter(Star.state >= 0)
    star_selection = sorted(star_selection, key=Star.hot, reverse=True)
    top_posts = []
    while len(top_posts) < min([15, len(star_selection)]):
        candidate = star_selection.pop(0)
        if candidate.oneup_count() > 0:
            top_posts.append(candidate)

    return render_template('group.html', group=group, stars=top_posts)


@app.route('/stars/', methods=["POST"])
@http_auth.login_required
def create_star():
    """Post a new Star"""
    pass


@app.route('/login', methods=["GET", "POST"])
@http_auth.login_required
def login():
    """Login a user"""
    form = LoginForm()
    if form.validate_on_submit():
        form.user.authenticated = True
        db.session.add(form.user)
        db.session.commit()
        if not form.user.active:
            flash("Please click the link in the validation email we sent you to activate your account.")
        else:
            login_user(form.user, remember=True)
            session["active_persona"] = form.user.active_persona.id
            flash("Welcome back, {}".format(form.user.active_persona.username))
            app.logger.debug("User {} logged in with {}.".format(current_user, current_user.active_persona))
        return form.redirect(url_for('.index'))
    elif request.method == "POST":
        app.logger.error("Invalid password for email '{}'".format(form.email.data))
        form.password.errors.append("Invalid password.")
    return render_template('login.html', form=form)


@app.route('/logout', methods=["GET", "POST"])
@login_required
@http_auth.login_required
def logout():
    """Logout a user"""
    user = current_user
    user.authenticated = False
    db.session.add(user)
    db.session.commit()
    logout_user()
    session["active_persona"] = None
    app.logger.debug("{} logged out.".format(user))
    return redirect(url_for('.login'))


@app.route('/signup', methods=["GET", "POST"])
@http_auth.login_required
def signup():
    """Signup a new user"""
    from uuid import uuid4
    form = SignupForm()

    if form.validate_on_submit():
        created_dt = datetime.datetime.utcnow()
        user = User(
            id=uuid4().hex,
            email=form.email.data,
            created=created_dt,
            modified=created_dt,
            active=False)
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
            send_validation_email(user, db)
            login_user(user, remember=True)

            flash("Just one more step: Check your email and click on the confirmation link in the message we just sent you.".format(form.username.data))
            app.logger.debug("Created new account {} with active Persona {}.".format(user, persona))

        return form.redirect(url_for('.index'))
    return render_template('signup.html', form=form)


@app.route('/validate/<id>/<signup_code>', methods=["GET"])
@http_auth.login_required
def signup_validation(id, signup_code):
    """Validate a user's email adress"""

    user = User.query.get(id)

    if user is None:
        flash("This signup link is invalid.")

    elif user.active:
        flash("Your account is already activated. You're good to go.")

    elif not user.valid_signup_code(signup_code):
        app.logger.error("User {} tried validating with invalid signup code {}.".format(user, signup_code))
        send_validation_email(user, db)
        flash("Oops! Invalid signup code. We have sent you another confirmation email. Please try clicking the link in that new email. ", "error")
    else:
        login_user(user, remember=False)
        session["active_persona"] = user.active_persona.id
        user.active = True
        db.session.add(user)
        db.session.commit()
        app.logger.info("{} activated their account.".format(user))
        flash("Yay! Welcome to RKTIK.")
    return redirect(url_for('.index'))
