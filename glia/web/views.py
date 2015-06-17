# -*- coding: utf-8 -*-
"""
    glia.views
    ~~~~~

    Implements views for Glia webapp

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import datetime
import traceback

from flask import request, redirect, render_template, flash, url_for, session, \
    current_app
from flask.ext.login import login_user, logout_user, current_user, login_required
from forms import LoginForm, SignupForm, CreateMovementForm, CreateReplyForm, \
    DeleteThoughtForm, CreateThoughtForm, CreatePersonaForm
from uuid import uuid4
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from . import app
from .. import socketio
from glia.web.dev_helpers import http_auth
from glia.web.helpers import send_validation_email, process_attachments, \
    send_external_notifications
from nucleus.nucleus import ALLOWED_COLORS
from nucleus.nucleus.database import db
from nucleus.nucleus.models import Persona, User, Movement, PersonaAssociation, \
    Thought, Mindset, Percept, MovementMemberAssociation, Tag, TagPercept, \
    PerceptAssociation, TextPercept, MentionNotification, Mention, Notification, \
    ReplyNotification


@app.before_request
def account_notifications():
    if not current_user.is_anonymous and not current_user.is_active:
        flash("Your account is not activated. Please click the link in the email that we sent you.")


@app.before_request
def mark_notifications_read():
    if not current_user.is_anonymous():
        notifications = Notification.query \
            .filter_by(url=request.path) \
            .filter_by(recipient=current_user.active_persona) \
            .filter_by(unread=True)

        for n in notifications:
            n.unread = False
            db.session.add(n)
            app.logger.info("Marked {} read".format(n))

        db.session.commit()


@app.route('/debug/')
@http_auth.login_required
def debug():
    """ Display raw data """
    thoughts = Thought.query.all()
    percepts = Percept.query.all()
    movements = Movement.query.all()
    mindsets = Mindset.query.all()
    users = User.query.all()

    return render_template(
        'debug.html',
        thoughts=thoughts,
        users=users,
        percepts=percepts,
        movements=movements,
        mindsets=mindsets
    )


@app.route('/', methods=["GET"])
@login_required
@http_auth.login_required
def index():
    """Front page"""
    movementform = CreateMovementForm()

    def movement_sort(movement):
        s = movement.mindspace.index \
            .filter(Thought.state >= 0) \
            .order_by(Thought.created.desc()) \
            .first()
        return s.created if s is not None else datetime.datetime.fromtimestamp(0)

    movements = current_user.active_persona.movements_followed
    movement_data = []
    for g in sorted(movements, key=movement_sort, reverse=True):
        g_thought_selection = g.mindspace.index.filter(Thought.state >= 0)
        g_top_posts = sorted(g_thought_selection, key=Thought.hot, reverse=True)[:3]

        recent_blog_post = g.blog.index.order_by(Thought.created.desc()).first()
        if recent_blog_post and datetime.datetime.utcnow() \
                - recent_blog_post.created > datetime.timedelta(days=1):
            recent_blog_post = None

        movement_data.append({
            'movement': g,
            'top_posts': g_top_posts,
            'recent_blog_post': recent_blog_post
        })

    more_movements = Movement.query \
        .join(MovementMemberAssociation) \
        .filter(MovementMemberAssociation.persona_id !=
            current_user.active_persona.id) \
        .order_by(func.count(MovementMemberAssociation.persona_id)) \
        .group_by(MovementMemberAssociation.persona_id) \
        .group_by(Movement)

    # Collect main page content
    top_post_selection = Thought.query.filter(Thought.state >= 0)
    top_post_selection = sorted(top_post_selection, key=Thought.hot, reverse=True)
    top_posts = []
    while len(top_posts) < min([9, len(top_post_selection)]):
        candidate = top_post_selection.pop(0)
        if candidate.oneup_count() > 0:
            top_posts.append(candidate)

    return render_template('index.html', movementform=movementform,
        movement_data=movement_data, top_posts=top_posts, more_movements=more_movements)


@app.route('/movement/', methods=["GET", "POST"])
@login_required
@http_auth.login_required
def movements(id=None):
    """Create movements"""
    form = CreateMovementForm(id=id)

    # Create a movement
    if form.validate_on_submit():
        movement_id = uuid4().hex
        movement_created = datetime.datetime.utcnow()
        movement = Movement(
            id=movement_id,
            username=form.name.data,
            description=form.mission.data,
            admin=current_user.active_persona,
            created=movement_created,
            modified=movement_created,
            color=form.color.data)
        current_user.active_persona.toggle_movement_membership(movement=movement, role="admin")
        try:
            db.session.add(movement)
            db.session.commit()
        except Exception, e:
            app.logger.exception("Error creating movement: {}".format(e))
            flash("There was a problem creating your movement. Please try again.")
        else:
            flash("Your new movement is ready!")
            app.logger.debug("{} created new movement {}".format(current_user.active_persona, movement))
            return redirect(url_for('.movement', id=movement_id))

    return render_template("movements.html", form=form, allowed_colors=ALLOWED_COLORS.keys())


@app.route('/thought/<id>/')
@http_auth.login_required
def thought(id=None):
    thought = Thought.query.get_or_404(id)

    # Load conversation context
    context = []
    while(len(context) < thought.context_length) and thought.parent is not None:
        context.append(thought.parent if len(context) == 0 else context[-1].parent)
        if context[-1].parent is None:
            break
    context = context[::-1]  # reverse list

    if thought.state < 0 and not thought.author.controlled():
        flash("This Thought is currently unavailable.")
        return(redirect(request.referrer or url_for('.index')))

    reply_form = CreateReplyForm(parent=thought.id)

    return render_template("thought.html", thought=thought, context=context,
        reply_form=reply_form)


@app.route('/tag/<name>/')
@http_auth.login_required
def tag(name):
    tag = Tag.query.filter_by(name=name).first()

    thoughts = Thought.query.join(PerceptAssociation).join(TagPercept).filter(TagPercept.tag_id == tag.id)

    return render_template("tag.html", tag=tag, thoughts=thoughts)


@app.route('/thought/<id>/delete', methods=["GET", "POST"])
@http_auth.login_required
def delete_thought(id=None):
    thought = Thought.query.get_or_404(id)
    form = DeleteThoughtForm()

    if not thought.author.controlled():
        flash("You are not allowed to change {}'s Thoughts".format(thought.author.username))
        app.logger.error("Tried to change visibility of {}'s Thoughts".format(thought.author))
        return redirect(request.referrer or url_for('.index'))

    if form.validate_on_submit():
        if thought.state == -2:
            thought.set_state(0)
        else:
            thought.set_state(-2)

        try:
            db.session.add(thought)
            db.session.commit()
        except:
            app.logger.error("Error setting publish state of {}\n{}".format(thought, traceback.format_exc()))
            db.session.rollback()
        else:
            flash("Updated visibility of {}".format(thought))

            app.logger.info("Thought {} set to publish state {}".format(id, thought.state))
            return(redirect(url_for(".thought", id=thought.id)))

    return render_template("delete_thought.html", thought=thought, form=form)


@app.route('/persona/create', methods=["GET", "POST"])
@app.route('/movement/<for_movement>/create_persona', methods=["GET", "POST"])
@http_auth.login_required
def create_persona(for_movement=None):
    """View for creating a new persona"""
    form = CreatePersonaForm()

    movement = None
    if for_movement:
        movement = Movement.query.get_or_404(for_movement)

    if form.validate_on_submit():
        created_dt = datetime.datetime.utcnow()
        persona = Persona(
            id=uuid4().hex,
            username=form.username.data,
            created=created_dt,
            modified=created_dt,
            color=form.color.data)

        # Create keypairs
        app.logger.info("Generating private keys for {}".format(persona))
        persona.generate_keys(form.password.data)

        db.session.add(persona)

        current_user.active_persona = persona
        db.session.add(current_user)

        association = PersonaAssociation(
            user=current_user, persona=persona)
        db.session.add(association)

        notification = Notification(
            text="Welcome to RKTIK, {}!".format(persona.username),
            recipient=persona,
            source="system"
        )
        db.session.add(notification)

        if movement:
            persona.toggle_movement_membership(movement=movement)

        try:
            db.session.commit()
        except SQLAlchemyError, e:
            app.logger.error("Error creating new Persona: {}".format(e))
            db.session.rollback()
            flash("Sorry! There was an error creating your new Persona. Please try again.", "error")
        else:
            if movement:
                flash("Your new Persona {} is now a member of {}".format(persona.username, movement.username))
                app.logger.debug("Created new Persona {} for user {} and joined {}.".format(
                    persona, current_user, movement))
                return redirect(url_for("web.movement_mindspace", id=movement.id))
            else:
                app.logger.debug("Created new Persona {} for user {}.".format(persona, current_user))
                return redirect(url_for("web.persona", id=persona.id))
    return render_template('create_persona.html',
        form=form, movement=movement, movement_id=for_movement, allowed_colors=ALLOWED_COLORS.keys())


@app.route('/persona/<id>/activate')
@http_auth.login_required
def activate_persona(id):
    """Activate a Persona and redirect to origin"""
    p = Persona.query.get_or_404(id)
    current_user.active_persona = p
    try:
        db.session.add(current_user)
        db.session.commit()
    except SQLAlchemyError, e:
        db.session.rollback()
        flash("There was an error activating your Persona. Please try again.")
        app.logger.error(
            "Error switching active persona on user {}\n{}".format(
                current_user, e))
    else:
        app.logger.info("{} activated {}".format(current_user, p))
    return redirect(request.referrer or url_for("web.index"))


@app.route('/persona/<id>/')
@http_auth.login_required
def persona(id=None):
    persona = Persona.query.get_or_404(id)

    if persona == current_user.active_persona:
        chat = current_user.active_persona.mindspace
    else:
        chat = Mindset.query.join(Persona, Mindset.id == persona.mindspace_id)

    movements = MovementMemberAssociation.query \
        .filter_by(active=True) \
        .filter_by(persona_id=persona.id)

    return(render_template('persona.html', chat=chat, persona=persona, movements=movements))


@app.route('/notifications')
@app.route('/notifications/page-<page>')
@login_required
@http_auth.login_required
def notifications(page=1):
    notifications = current_user.active_persona \
        .notifications \
        .order_by(Notification.modified.desc()) \
        .paginate(page, 25)

    return(render_template('notifications.html',
        notifications=notifications))


@app.route('/movement/<id>/')
@login_required
@http_auth.login_required
def movement(id):
    """Redirect user depending on whether he is a member or not"""
    movement = Movement.query.get_or_404(id)
    if movement.current_role() in ["member", "admin"]:
        rv = redirect(url_for("web.movement_mindspace", id=id))
    else:
        rv = redirect(url_for("web.movement_blog", id=id))
    return rv


@app.route('/movement/<id>/mindspace', methods=["GET"])
@login_required
@http_auth.login_required
def movement_mindspace(id):
    """Display a movement's profile"""
    movement = Movement.query.get(id)
    if not movement:
        flash("Movement not found")
        app.logger.warning("Movement '{}' not found. User: {}".format(
            id, current_user))
        return(redirect(url_for('.movements')))

    thought_selection = movement.mindspace.index.filter(Thought.state >= 0)
    thought_selection = sorted(thought_selection, key=Thought.hot, reverse=True)
    top_posts = []
    while len(top_posts) < min([15, len(thought_selection)]):
        candidate = thought_selection.pop(0)
        candidate.promote_target = None if candidate in movement.blog \
            else movement
        if candidate.oneup_count() > 0:
            top_posts.append(candidate)

    recent_blog_post = movement.blog.index.order_by(Thought.created.desc()).first()
    if recent_blog_post and datetime.datetime.utcnow() \
            - recent_blog_post.created > datetime.timedelta(days=1):
        recent_blog_post = None

    return render_template('movement_mindspace.html',
        movement=movement, thoughts=top_posts, recent_blog_post=recent_blog_post)


@app.route('/movement/<id>/blog/', methods=["GET"])
@app.route('/movement/<id>/blog/page-<int:page>/', methods=["GET"])
@login_required
@http_auth.login_required
def movement_blog(id, page=1):
    """Display a movement's profile"""
    movement = Movement.query.get_or_404(id)

    thought_selection = movement.blog.index \
        .filter_by(author_id=movement.id) \
        .filter(Thought.state >= 0) \
        .order_by(Thought.created.desc()) \
        .paginate(page, 5)

    return render_template('movement_blog.html', movement=movement, thoughts=thought_selection)


@app.route('/create', methods=["GET", "POST"])
@http_auth.login_required
def create_thought():
    """Post a new Thought"""

    form = CreateThoughtForm()
    thought_created = datetime.datetime.utcnow()
    thought_id = uuid4().hex
    author = current_user.active_persona
    sm = None
    parent = None

    # Prepopulate form if redirected here from chat
    if not form.longform.raw_data and "text" in request.args:
        form.longform.data = request.args.get("text")

    if "mindset" in request.args:
        form.mindset.data = request.args['mindset']

    if "parent" in request.args:
        form.parent.data = request.args['parent']

    sm = Mindset.query.get_or_404(form.mindset.data)
    parent = Thought.query.get_or_404(form.parent.data) if form.parent.data else None

    if form.validate_on_submit():
        thought = Thought(
            id=thought_id,
            text=form.text.data,
            author=author,
            parent=parent,
            created=thought_created,
            modified=thought_created,
            mindset_id=sm.id)
        db.session.add(thought)

        text, percepts = process_attachments(thought.text)
        thought.text = text

        if len(form.longform.data) > 0:
            lftext, lfpercepts = process_attachments(form.longform.data)
            percepts = percepts + lfpercepts

            lftext_percept = TextPercept.get_or_create(lftext,
                source=form.lfsource.data)
            percepts.append(lftext_percept)

        for percept in percepts:
            db.session.add(percept)

            if isinstance(percept, Mention):
                notification = MentionNotification(percept,
                    author, url_for('web.thought', id=thought_id))
                send_external_notifications(notification)
                db.session.add(notification)

            assoc = PerceptAssociation(thought=thought, percept=percept, author=author)
            thought.percept_assocs.append(assoc)
            app.logger.info("Attached {} to new {}".format(percept, thought))
            db.session.add(assoc)

        if parent:
            notif = ReplyNotification(parent_thought=parent, author=author,
                url=url_for('web.thought', id=thought_id))
            send_external_notifications(notif)
            db.session.add(notif)

        try:
            db.session.commit()
        except SQLAlchemyError, e:
            db.session.rollback()
            app.logger.error("Error creating longform thought: {}".format(e))
            flash("An error occured saving your message. Please try again.")
        else:
            app.logger.info(u"{} {}: {}".format(sm, author.username, thought.text))

            # Render using templates
            thought_macros_template = current_app.jinja_env.get_template(
                'macros/thought.html')
            thought_macros = thought_macros_template.make_module(
                {'request': request})

            data = {
                'username': author.username,
                'msg': render_template("chatline.html", thought=thought),
                'thought_id': thought_id,
                'parent_id': thought.parent_id,
                'parent_short': thought_macros.short(thought.parent) if thought.parent else None,
                'vote_count': thought.oneup_count()
            }
            socketio.emit('message', data, room=form.mindset.data)

            reply_data = {
                'msg': thought_macros.comment(thought),
                'parent_id': form.parent.data
            }
            socketio.emit('comment', reply_data, room=form.parent.data)
            flash("Great success! Your new post is ready.")
            return redirect(url_for("web.thought", id=thought_id))

    return render_template("create_thought.html",
        form=form, mindset=sm, parent=parent)


@app.route('/login', methods=["GET", "POST"])
@http_auth.login_required
def login():
    """Login a user"""
    if not current_user.is_anonymous():
        return redirect(url_for("web.index"))

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

    if not current_user.is_anonymous():
        return redirect(url_for("web.index"))

    if form.validate_on_submit():
        created_dt = datetime.datetime.utcnow()
        persona = Persona(
            id=uuid4().hex,
            username=form.username.data,
            created=created_dt,
            modified=created_dt,
            color=form.color.data)

        # Create keypairs
        app.logger.info("Generating private keys for {}".format(persona))
        persona.generate_keys(form.password.data)

        db.session.add(persona)

        notification = Notification(
            text="Welcome to RKTIK, {}!".format(persona.username),
            recipient=persona,
            source="system"
        )
        db.session.add(notification)

        created_dt = datetime.datetime.utcnow()
        user = User(
            id=uuid4().hex,
            email=form.email.data,
            active_persona=persona,
            created=created_dt,
            modified=created_dt)
        user.set_password(form.password.data)
        db.session.add(user)

        association = PersonaAssociation(
            user=user, persona=persona)
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

            flash("Welcome to RKTIK! Click the link in the activation email we just sent you to be able to reset your account when you loose your password.".format(form.username.data))
            app.logger.debug("Created new account {} with active Persona {}.".format(user, persona))

        return form.redirect(url_for('web.index'))
    return render_template('signup.html', form=form, allowed_colors=ALLOWED_COLORS.keys())


@app.route('/validate/<id>/<signup_code>', methods=["GET"])
@http_auth.login_required
def signup_validation(id, signup_code):
    """Validate a user's email adress"""

    user = User.query.get(id)

    if user is None:
        flash("This signup link is invalid.")

    elif user.validated:
        flash("Your email address is already validated. You're good to go.")

    elif not user.valid_signup_code(signup_code):
        app.logger.error("User {} tried validating with invalid signup code {}.".format(user, signup_code))
        send_validation_email(user, db)
        flash("Oops! Invalid signup code. We have sent you another confirmation email. Please try clicking the link in that new email. ", "error")
    else:
        login_user(user, remember=False)
        session["active_persona"] = user.active_persona.id
        user.validate()
        db.session.add(user)
        db.session.commit()
        app.logger.info("{} validated their email address.".format(user))
        flash("Your email address is now verified.")
    return redirect(url_for('.index'))
