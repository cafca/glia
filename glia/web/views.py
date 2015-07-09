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
    DeleteThoughtForm, CreateThoughtForm, CreatePersonaForm, InviteMembersForm
from uuid import uuid4
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from . import app, VIEW_CACHE_TIMEOUT
from .. import socketio
from glia.web.dev_helpers import http_auth
from glia.web.helpers import send_validation_email, \
    send_external_notifications, send_movement_invitation, \
    valid_redirect, make_view_cache_key
from nucleus.nucleus import ALLOWED_COLORS
from nucleus.nucleus.database import db, cache
from nucleus.nucleus.models import Persona, User, Movement, \
    Thought, Mindset, MovementMemberAssociation, Tag, TagPercept, \
    PerceptAssociation, Notification, \
    Mindspace, Blog, Dialogue

#
# UTILITIES
#


@app.before_request
def account_notifications():
    if not current_user.is_anonymous and not current_user.is_active:
        flash("Your account is not activated. Please click the link in the email that we sent you.")


@app.before_request
def mark_notifications_read():
    """Mark notifications for the current request path as read"""

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

#
# ROUTES
#


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


@app.route('/persona/create', methods=["GET", "POST"])
@app.route('/movement/<for_movement>/create_persona', methods=["GET", "POST"])
@http_auth.login_required
def create_persona(for_movement=None):
    """View for creating a new persona"""
    form = CreatePersonaForm()

    movement = None
    if for_movement:
        code = request.args.get("invitation_code", default=None)
        movement = Movement.query.get_or_404(for_movement)

    if form.validate_on_submit():
        created_dt = datetime.datetime.utcnow()
        persona = Persona(
            id=uuid4().hex,
            username=form.username.data,
            created=created_dt,
            modified=created_dt,
            color=form.color.data,
            user=current_user)

        # Create keypairs
        app.logger.info("Generating private keys for {}".format(persona))
        persona.generate_keys(form.password.data)

        # Create mindspace and blog
        persona.mindspace = Mindspace(
            id=uuid4().hex,
            author=persona)

        persona.blog = Blog(
            id=uuid4().hex,
            author=persona)

        db.session.add(persona)

        current_user.active_persona = persona
        db.session.add(current_user)

        notification = Notification(
            text="Welcome to RKTIK, {}!".format(persona.username),
            recipient=persona,
            source="system",
            url=url_for("web.persona", id=persona.id)
        )
        db.session.add(notification)

        if movement:
            persona.toggle_movement_membership(movement=movement, code=code)

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


@app.route('/create', methods=["GET", "POST"])
@login_required
@http_auth.login_required
def create_thought():
    """Post a new Thought"""

    form = CreateThoughtForm()
    ms = None
    parent = None
    thought_data = None

    # Prepopulate form if redirected here from chat
    if not form.longform.raw_data and "text" in request.args:
        form.longform.data = request.args.get("text")

    if "parent" in request.args and request.args['parent'] is not None:
        form.parent.data = request.args['parent']
    parent = Thought.query.get_or_404(form.parent.data) if form.parent.data else None

    if request.args.get("mindset"):
        form.mindset.data = request.args['mindset']
    elif parent is not None:
        ms = parent.mindset
    else:
        flash("New thoughts needs either a parent or a mindset to live in.")
        app.logger.error("Neither parent nor mindset given {}")

    ms = Mindset.query.get_or_404(form.mindset.data) if form.mindset.data else None

    if form.validate_on_submit():
        try:
            thought_data = Thought.create_from_input(
                text=form.text.data,
                longform=form.longform.data,
                longform_source=form.lfsource.data,
                parent=parent,
                mindset=ms)
        except ValueError, e:
            flash("There was an error creating your thought ({})".format(e))
            app.logger.error("Error creating new thought ({})".format(e))

        if thought_data is not None:
            thought = thought_data["instance"]
            thought.posted_from = "web-form"

            db.session.add(thought)
            db.session.add_all(thought_data["notifications"])

            try:
                db.session.commit()
            except SQLAlchemyError, e:
                db.session.rollback()
                app.logger.error("Error creating longform thought: {}".format(e))
                flash("An error occured saving your message. Please try again.")
            else:
                map(send_external_notifications, thought_data["notifications"])

                # Render using templates
                thought_macros_template = current_app.jinja_env.get_template(
                    'macros/thought.html')
                thought_macros = thought_macros_template.make_module(
                    {'request': request})

                data = {
                    'username': thought.author.username,
                    'msg': render_template("chatline.html", thought=thought),
                    'thought_id': thought.id,
                    'parent_id': thought.parent_id,
                    'parent_short': thought_macros.short(thought.parent) if thought.parent else None,
                    'vote_count': thought.upvote_count()
                }
                socketio.emit('message', data, room=form.mindset.data)

                socketio.emit('comment', {'msg': thought_macros.comment(thought),
                    'parent_id': form.parent.data}, room=form.parent.data)
                flash("Great success! Your new post is ready.")
                return redirect(url_for("web.thought", id=thought.id))

    return render_template("create_thought.html",
        form=form, mindset=ms, parent=parent)


@app.route('/thought/<id>/delete', methods=["GET", "POST"])
@login_required
@http_auth.login_required
def delete_thought(id=None):
    thought = Thought.query.get_or_404(id)
    form = DeleteThoughtForm()

    if not thought.authorize("delete", current_user.active_persona.id):
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


@app.route('/', methods=["GET"])
@http_auth.login_required
@cache.cached(
    timeout=VIEW_CACHE_TIMEOUT,
    key_prefix=make_view_cache_key
)
def index():
    """Front page"""
    movementform = CreateMovementForm()

    # Determine content source
    if current_user.is_anonymous():
        sources = more_movements = Movement.query \
            .filter(Movement.id.in_([m['id'] for m in Movement.top_movements()]))
    else:
        sources = current_user.active_persona.blogs_followed
        more_movements = Movement.query \
            .filter(Movement.id.in_(
                current_user.active_persona.suggested_movements()))

    sources = sorted(sources, key=lambda s: s.attention, reverse=True)

    blog_list = list()
    for s in sources:
        source_data = dict()
        source_data["ident"] = s
        source_data["blog"] = list(s.blog.index.order_by(Thought.created.desc()).limit(3))
        source_data["url"] = url_for('web.persona_blog', id=s.id) if isinstance(s, Persona) else s.get_absolute_url()
        if isinstance(s, Movement) and s.active_member():
            source_data["mindspace"] = Thought.query.filter(
                Thought.id.in_(s.mindspace_top_thought(count=3)))
        blog_list.append(source_data)

    # Collect main page content
    top_posts = Thought.query.filter(Thought.id.in_(Thought.top_thought()))

    return render_template('index.html', movementform=movementform,
        blog_list=blog_list, top_posts=top_posts, more_movements=more_movements)


@app.route('/movement/<movement_id>/invite', methods=["GET", "POST"])
@login_required
@http_auth.login_required
def invite_members(movement_id):
    """Let movments invite members by username or email adress"""
    movement = Movement.query.get_or_404(movement_id)
    invited = list()

    form = InviteMembersForm()
    if form.validate_on_submit():
        for handle in form.handles:
            if send_movement_invitation(handle, movement, message=form.message):
                app.logger.info("Invited {} to {}".format(handle, movement))
                invited.append(handle)
            else:
                flash("There was an error sending an invitation to {}. Please try again.".format(
                    handle), 'error')

    return render_template("movement_invite.html",
        form=form, movement=movement, invited=invited)


@app.route('/login', methods=["GET", "POST"])
@http_auth.login_required
def login():
    """Login a user"""
    if not current_user.is_anonymous() and current_user.is_authenticated():
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
            app.logger.debug("User {} logged in with {}.".format(current_user, current_user.active_persona))
        return form.redirect(valid_redirect(request.args.get('next'))or url_for('web.index'))
    elif request.method == "POST":
        app.logger.error("Invalid password for email '{}'".format(form.email.data))
        form.password.errors.append("Invalid password.")
    form_action = url_for('web.login', next=valid_redirect(request.args.get('next')))
    return render_template('login.html', form=form, form_action=form_action)


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


@app.route('/movement/<id>/')
@http_auth.login_required
def movement(id):
    """Redirect user depending on whether he is a member or not"""
    movement = Movement.query.get_or_404(id)
    if not current_user.is_anonymous() and movement.current_role() in ["member", "admin"]:
        rv = redirect(url_for("web.movement_mindspace", id=id))
    else:
        code = request.args.get('invitation_code', default=None)
        rv = redirect(url_for("web.movement_blog", id=id, invitation_code=code))
    return rv


@app.route('/movement/<id>/blog/', methods=["GET"])
@app.route('/movement/<id>/blog/page-<int:page>/', methods=["GET"])
@http_auth.login_required
@cache.cached(
    timeout=VIEW_CACHE_TIMEOUT,
    key_prefix=make_view_cache_key
)
def movement_blog(id, page=1):
    """Display a movement's profile"""
    movement = Movement.query.get_or_404(id)

    thought_selection = movement.blog.index \
        .filter_by(author_id=movement.id) \
        .filter(Thought.state >= 0) \
        .order_by(Thought.created.desc()) \
        .paginate(page, 5)

    code = request.args.get("invitation_code", default=None)
    return render_template('movement_blog.html', movement=movement,
        thoughts=thought_selection, code=code)


@app.route('/movement/<id>/mindspace', methods=["GET"])
@http_auth.login_required
@cache.cached(
    timeout=VIEW_CACHE_TIMEOUT,
    key_prefix=make_view_cache_key
)
def movement_mindspace(id):
    """Display a movement's profile"""
    movement = Movement.query.get(id)
    if not movement:
        flash("Movement not found")
        app.logger.warning("Movement '{}' not found. User: {}".format(
            id, current_user))
        return(redirect(url_for('.movements')))

    if movement.private and not movement.authorize("read", current_user.active_persona.id):
        flash("Only members can access the mindspace of '{}'".format(movement.username))
        return redirect(url_for("web.movement_blog", id=movement.id))

    thought_selection = movement.mindspace.index.filter(Thought.state >= 0)
    thought_selection = sorted(thought_selection, key=Thought.hot, reverse=True)
    top_posts = []

    for i in range(min([15, len(thought_selection)])):
        candidate = thought_selection.pop(0)
        candidate.promote_target = None if candidate in movement.blog \
            else movement
        if candidate.upvote_count() > 0:
            top_posts.append(candidate)

    member_selection = MovementMemberAssociation.query \
        .filter_by(movement=movement) \
        .filter_by(active=True) \
        .order_by(MovementMemberAssociation.last_seen.desc()) \
        .limit(10)

    return render_template('movement_mindspace.html',
        movement=movement, thoughts=top_posts,
        member_selection=member_selection)


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
            color=form.color.data,
            private=form.private.data)
        current_user.active_persona.toggle_movement_membership(movement=movement, role="admin")
        try:
            db.session.add(movement)
            db.session.commit()
        except Exception, e:
            app.logger.exception("Error creating movement: {}".format(e))
            flash("There was a problem creating your movement. Please try again.")
        else:
            app.logger.debug("{} created new movement {}".format(current_user.active_persona, movement))
            return redirect(url_for('.movement', id=movement_id))

    return render_template("movements.html", form=form, allowed_colors=ALLOWED_COLORS.keys())


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


@app.route('/persona/<id>/')
@http_auth.login_required
@cache.cached(
    timeout=VIEW_CACHE_TIMEOUT,
    key_prefix=make_view_cache_key
)
def persona(id):
    persona = Persona.query.get_or_404(id)

    if current_user.is_anonymous():
        chat = None
    elif persona == current_user.active_persona:
        chat = current_user.active_persona.mindspace
    else:
        chat = Dialogue.get_chat(persona, current_user.active_persona)
        if inspect(chat).persistent is False:
            app.logger.info('Storing {} in database'.format(chat))
            # chat object is newly created
            db.session.add(chat)
            try:
                db.session.commit()
            except SQLAlchemyError, e:
                db.session.rollback()
                flash("There was an error starting a dialogue with {}.".format(
                    persona.username))

                app.logger.error(
                    "Error creating dialogue between {} and {}\n{}".format(
                        current_user.active_persona, persona, e))
                chat = None

    movements = MovementMemberAssociation.query \
        .filter_by(active=True) \
        .filter_by(persona_id=persona.id)

    return(render_template('persona.html', chat=chat, persona=persona, movements=movements))


@app.route('/anonymous/blog/', methods=["GET"])
@app.route('/persona/<id>/blog/', methods=["GET"])
@app.route('/persona/<id>/blog/page-<int:page>/', methods=["GET"])
@http_auth.login_required
@cache.cached(
    timeout=VIEW_CACHE_TIMEOUT,
    key_prefix=make_view_cache_key
)
def persona_blog(id, page=1):
    """Display a persona's blog"""
    if id is None:
        return redirect(url_for('web.signup'))

    p = Persona.query.get_or_404(id)

    thought_selection = p.blog.index \
        .filter_by(author_id=p.id) \
        .filter(Thought.state >= 0) \
        .order_by(Thought.created.desc()) \
        .paginate(page, 5)

    return render_template('persona_blog.html', persona=p, thoughts=thought_selection)


@app.route('/signup', methods=["GET", "POST"])
@http_auth.login_required
def signup():
    """Signup a new user"""
    from uuid import uuid4
    form = SignupForm()
    mma = None

    invitation_code = request.args.get('invitation_code', default=None)
    if invitation_code:
        mma = MovementMemberAssociation.query.filter_by(invitation_code=invitation_code).first()
        if mma is None:
            flash("Can not find the movement you were invited to", "error")

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

        # Create mindspace and blog
        persona.mindspace = Mindspace(
            id=uuid4().hex,
            author=persona)

        persona.blog = Blog(
            id=uuid4().hex,
            author=persona)

        db.session.add(persona)

        if mma and not mma.active:
            mma.persona = persona
            mma.active = True
            mma.role = "member"
            db.session.add(mma)

        notification = Notification(
            text="Welcome to RKTIK, {}!".format(persona.username),
            recipient=persona,
            url="http://www.rktik.com/movement/27fe161d2ba64f4bb4986a99bebea18a/mindspace",
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

        persona.user = user
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

        rv = url_for('web.index') if mma is None else url_for('web.movement', id=mma.movement.id)
        if valid_redirect(request.args.get('next')):
            rv = valid_redirect(request.args.get('next'))
        return redirect(rv)

    if request.method == "GET":
        if not current_user.is_anonymous():
            if mma:
                if mma.active:
                    flash("This activation code has been used before. You can try joining the movement by clicking the join button below.")
                else:
                    flash("You were invited to join this movement. Click the \"Join movement\" button on the bottom of this page to do so.")
                return redirect(url_for('web.movement', id=mma.movement.id, invitation_code=mma.invitation_code))
            else:
                return redirect(url_for("web.index"))

    kwargs = dict()
    if mma:
        kwargs["invitation_code"] = mma.invitation_code

    if valid_redirect(request.args.get('next')):
        kwargs['next'] = valid_redirect(request.args.get('next'))

    form_url = url_for('web.signup', **kwargs)

    return render_template('signup.html',
        form=form, form_url=form_url, allowed_colors=ALLOWED_COLORS.keys(),
        mma=mma)


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


@app.route('/tag/<name>/')
@http_auth.login_required
@cache.cached(
    timeout=VIEW_CACHE_TIMEOUT
)
def tag(name):
    tag = Tag.query.filter_by(name=name).first()

    thoughts = Thought.query.join(PerceptAssociation).join(TagPercept).filter(TagPercept.tag_id == tag.id)

    return render_template("tag.html", tag=tag, thoughts=thoughts)


@app.route('/thought/<id>/')
@http_auth.login_required
@cache.cached(
    timeout=VIEW_CACHE_TIMEOUT,
    key_prefix=make_view_cache_key
)
def thought(id=None):
    thought = Thought.query.get_or_404(id)

    if not thought.authorize("read", current_user.active_persona.id):
        flash("This Thought is private")
        return(redirect(url_for("web.index")))

    # Load conversation context
    context = []
    while(len(context) < thought.context_length) and thought.parent is not None:
        context.append(thought.parent if len(context) == 0 else context[-1].parent)
        if context[-1].parent is None:
            break
    context = context[::-1]  # reverse list

    if thought.state < 0 and not thought.authorize("delete", current_user.active_persona.id):
        flash("This Thought is currently unavailable.")
        if request.referrer and request.referrer != request.url:
            redirect_target = request.referrer
        else:
            redirect_target = url_for('web.index')
        return redirect(redirect_target)

    reply_form = CreateReplyForm(parent=thought.id)

    return render_template("thought.html", thought=thought, context=context,
        reply_form=reply_form)
