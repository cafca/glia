# -*- coding: utf-8 -*-
"""
    glia.helpers
    ~~~~~

    Implements helper functionality for rendering Rktik web site

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import logging
import os
import pytz
import sendgrid

from flask import render_template, request
from flask.ext.login import current_user
from hashlib import sha256
from uuid import uuid4
from sendgrid import SendGridClient, SendGridClientError, SendGridServerError
from sqlalchemy.exc import SQLAlchemyError

from nucleus.nucleus.models import Persona, Movement, \
    MovementMemberAssociation, Thought

from .. import socketio


logger = logging.getLogger('web')

# Cached results are fetched from the database by ID, which returns the result
# list out of order. This lambda function reorders them.
reorder = lambda l: sorted(l, key=Thought.hot, reverse=True)


class UnauthorizedError(Exception):
    """Current user is not authorized for this action"""
    pass


def authorize_filter(obj, action, actor=None):
    """Return True if action on obj is authorized for active Persona or
    given Persona

    Args:
        obj (nucleus.models.Serializable): Implements the authorize method
        action (String): One of the actions defined in Nucleus
        actor (Identity): Optional identity to check for

    Returns:
        Boolean: True if action is currently authorized
    """
    if actor is None:
        actor = current_user.active_persona

    return obj.authorize(action, actor.id)


def generate_graph(thoughts):
    """Generates a graph for consumption by the D3 force layout

    frontpage
        +--+ Thought1 +--+ Thought1_Author
        |
        +--+ Thought2 +--+ Thought2-4_Author
        |                |
        .    Thought3 +--+
        .    (not frontpage)
        .                |
             Thought4 +--+
             (not frontpage)
                                       
    Args:
        thoughts (list): List of thought objects

    Returns:
        dict: Dictionary with keys 'nodes', 'links' at the root level,
            both containing a list of dicts for each item. Node items have
            keys 'name' and 'group' (for coloring). Link items have an 'source'
            and 'target' key, each containing an index for items in the 'nodes'
            list.
    """
    rv = dict(nodes=[], links=[])
    node_indexes = dict()

    if current_user.is_anonymous():
        movements = {m.id: m for m in Movement.query
            .filter(Movement.id.in_([m['id'] for m in Movement.top_movements()]))}
    else:
        movements = {m.id: m for m in current_user.active_persona.blogs_followed}

    thought_item = lambda t: {
        "name": "{}<br /><small>by {}</small>".format(
            t.text.encode('utf-8'), t.author.username.encode('utf-8')),
        "group": 1,
        "radius": 2,
        "url": t.get_absolute_url(),
        "anim": (5.0 / (t.hot() * 1000 + 1))
    }

    ident_item = lambda ident: {
        "name": ident.username,
        "group": 2,
        "radius": 4,
        "url": ident.get_absolute_url(),
        "color": ident.color
    }

    rv['nodes'].append({
        "name": "Rktik Mind",
        "group": 0,
        "radius": 6,
        "fixed": True,
        "x": 100,
        "y": 100
    })
    i = 1

    for t in thoughts:
        if t.id in node_indexes:
            rv["links"].append({"source": 0, "target": node_indexes[t.id]})
        else:
            rv["nodes"].append(thought_item(t))
            rv["links"].append({"source": 0, "target": i})

            node_indexes[t.id] = i
            i += 1

        if t.author.id not in node_indexes:
            rv["nodes"].append(ident_item(t.author))
            node_indexes[t.author.id] = i
            try:
                del movements[t.author.id]
            except KeyError:
                pass
            i += 1

        rv["links"].append({"source": node_indexes[t.id],
            "target": node_indexes[t.author.id]})

        for t_blog in t.author.blog.index:
            if t_blog != t:
                if t_blog.id not in node_indexes:
                    rv["nodes"].append(thought_item(t_blog))
                    node_indexes[t_blog.id] = i
                    i += 1

                rv["links"].append({"target": node_indexes[t.author.id],
                    "source": node_indexes[t_blog.id]})

    for m in movements.values():
        rv["nodes"].append(ident_item(m))
        node_indexes[m.id] = i
        i += 1

        for t_blog in m.blog.index:
            if t_blog.id not in node_indexes:
                rv["nodes"].append(thought_item(t_blog))
                node_indexes[t_blog.id] = i
                i += 1

                rv["links"].append({"target": node_indexes[m.id],
                    "source": node_indexes[t_blog.id]})

    return rv


def localtime(value, tzval="UTC"):
    """Convert tz-naive UTC datetime into tz-naive local datetime

    Args:
        value (datetime): timezone naive UTC datetime
        tz (sting): timezone e.g. 'Europe/Berlin' (see pytz references)
    """
    value = value.replace(tzinfo=pytz.utc)  # assuming value is utc time
    value = value.astimezone(pytz.timezone(tzval))  # convert to local time (tz-aware)
    value = value.replace(tzinfo=None)  # make tz-naive again
    return value


def make_view_cache_key(*args, **kwargs):
    """Make a cache key for view function depending on logged in user and path

    Returns:
        string: Cache key for use by Flask-Cache
    """
    persona = current_user.active_persona.id if not current_user.is_anonymous() else "anon"
    url = request.url
    rv = "-".join([persona, url]).encode('utf-8')
    return sha256(rv).hexdigest()


def send_email(message):
    """Send Email using Sendgrid service

    Args:
        message (Sendgrid Message): Readily configured message object

    Returns:
        tuple: (status, message)

    Raises:
        SendGridClientError
        SendGridServerError
    """
    from flask import current_app

    sg_user = os.environ.get('SENDGRID_USERNAME') or current_app.config["SENDGRID_USERNAME"]
    sg_pass = os.environ.get('SENDGRID_PASSWORD') or current_app.config["SENDGRID_PASSWORD"]
    sg = SendGridClient(sg_user, sg_pass, raise_errors=True)
    try:
        rv = sg.send(message)
    except Exception, e:
        logger.exception("Eror sending email: {}".format(e))
        rv = (None, None)

    return rv


def send_external_notifications(notification):
    """Send Email and trigger Desktop notifications depending on user prefs

    Args:
        notification (Notification): Notification object specifying message
            recipient etc.
    """

    # Desktop notifications
    if isinstance(notification.recipient, Persona):
        data = {
            'title': notification.source,
            'msg': notification.text
        }
        socketio.emit('message', data,
            room=notification.recipient.id, namespace="/personas")

    # Email notification
    if isinstance(notification.recipient, Persona):
        if notification.recipient.user.email_allowed(notification):
            message = sendgrid.Mail()
            message.add_to("{} <{}>".format(
                notification.recipient.username, notification.recipient.user.email))
            message.set_subject(notification.text)
            message.set_html(render_template("email/notification.html",
                notification=notification))
            message.set_from('RKTIK Notifications')

            logger.info("Sending email notification to {}: {}".format(
                notification.recipient, notification.recipient.user.email))

            try:
                status, msg = send_email(message)
            except SendGridClientError, e:
                logger.error("Client error sending notification email: {}".format(e))
            except SendGridServerError, e:
                logger.error("Server error sending notification email: {}".format(e))


def send_movement_invitation(recipient, movement, personal_message=None):
    """Send an email invitation to a user, asking them to join a movement

    Args:
        recipient (String): Recipient email address
        movement (Movement): Movement to which the recipient will be invited
        message (String): Optional personal message from the inviter
    """
    from nucleus.nucleus.database import db

    mma = MovementMemberAssociation(
        movement=movement,
        role="invited",
        active=False,
        invitation_code=uuid4().hex)

    db.session.add(mma)

    if not isinstance(movement, Movement):
        raise ValueError("{} is not a valid movement instance".format(
            movement))

    message = sendgrid.Mail()
    message.add_to(recipient)
    message.set_subject("You were invited to join the {} movement".format(
        movement.username))
    message.set_html(render_template("email/movement_invitation.html",
        movement=movement,
        sender=current_user.active_persona,
        personal_message=personal_message,
        invitation_code=mma.invitation_code))
    message.set_from('RKTIK {} movement'.format(movement.username))

    try:
        db.session.commit()
        status, msg = send_email(message)
    except (SendGridClientError, SendGridServerError), e:
        logger.error("Error sending email invitation to '{}' code '{}': {}".format(
            recipient, mma.invitation_code, e))
    except SQLAlchemyError, e:
        logger.error("Error sending email invitation to '{}' code '{}': {}".format(
            recipient, mma.invitation_code, e))
    else:
        logger.info("Sent invitation email for {} to '{}'".format(
            movement, recipient))
        return mma


def send_validation_email(user, db):
    """Send validation email using sendgrid, resetting the signup code.

    Args:
        user (User): Nucleus user object
        db (SQLAlchemy): Database used to store user's new signup code

    Throws:
        ValueError: If active user has no name or email address
    """
    from nucleus.nucleus.database import db
    from flask import current_app

    user.signup_code = uuid4().hex
    db.session.add(user)
    db.session.commit()

    name = user.active_persona.username
    email = user.email

    if name is None or email is None:
        raise ValueError("Username and email can't be empty")

    message = sendgrid.Mail()
    message.add_to("{} <{}>".format(name, email))
    message.set_subject('Please confirm your email address')
    message.set_html(render_template("email/signup_confirmation.html", user=user))
    message.set_from('RKTIK Email Confirmation')

    try:
        status, msg = send_email(message)
    except SendGridClientError, e:
        logger.error("Client error sending confirmation email: {}".format(e))
        if current_app.config.get('DEBUG') is True:
            logger.warning("User is being auto validated in debug environment")
            user.validate()
    except SendGridServerError, e:
        logger.error("Server error sending confirmation email: {}".format(e))
        logger.warning("User is being auto validated in debug environment")
        user.validate()


def valid_redirect(path):
    """Return True if path is in rktik domain"""
    from flask import current_app
    return path if path and path.startswith(current_app.config.get('SERVER_HOST')) else None
