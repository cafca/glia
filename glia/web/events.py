# -*- coding: utf-8 -*-
"""
    glia.events
    ~~~~~

    Socket.IO server for event handling

    :copyright: (c) 2015 by Vincent Ahrend.
"""

import datetime
import functools

from flask import request, current_app, url_for
from flask.ext.login import current_user
from flask.ext.socketio import emit, join_room, leave_room
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError

from . import app
from .. import socketio, db
from glia.web.helpers import process_attachments, find_mentions, \
    send_external_notifications
from nucleus.nucleus.models import Mindset, Thought, PlanetAssociation, Movement, \
    Persona, Mention, MentionNotification, ReplyNotification
from nucleus.nucleus import notification_signals, PersonaNotFoundError, \
    UnauthorizedError

# Create blinker signal namespace
local_model_changed = notification_signals.signal('local-model-changed')


def socketio_authenticated_only(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated():
            request.namespace.disconnect()
        else:
            return f(*args, **kwargs)
    return wrapped


#
# PERSONAL WEBSOCKET
#


@socketio.on_error(namespace='/personas')
def chat_error_handlerp(e):
    app.logger.error('An error has occurred: ' + str(e))


@socketio_authenticated_only
@socketio.on('connect', namespace="/personas")
def connectp():
    request.namespace.join_room(current_user.active_persona.id)
    app.logger.info("{} logged in".format(current_user.active_persona))


#
# MOVEMENT WEBSOCKET
#


@socketio_authenticated_only
@socketio.on('joined', namespace='/movements')
def joined(message):
    """Sent by clients when they enter a room.
    A status message is broadcast to all people in the room."""
    if not current_user.is_active():
        app.logger.info("Inactive users can't join chat")
    else:
        if "room_id" not in message:
            message["room_id"] = "base"

        current_user.active_persona.last_connected = datetime.datetime.utcnow()
        db.session.add(current_user.active_persona)
        db.session.commit()

        join_room(message["room_id"])
        app.logger.info("{} joined movement chat {}".format(current_user.active_persona, message['room_id']))
        emit('status', {'msg': current_user.active_persona.username + ' has entered the room.'}, room=message["room_id"])

        rv = {"nicknames": [], "ids": []}
        movement = Movement.query.filter_by(blog_id=message["room_id"]).first()
        room = Mindset.query.get(message["room_id"])
        if room and isinstance(room.author, Movement):
            movement = room.author
            online_cutoff = datetime.datetime.utcnow() - \
                datetime.timedelta(seconds=15 * 60)
            for gma in movement.members.join(Persona).filter(
                    Persona.last_connected > online_cutoff).order_by(
                    Persona.last_connected.desc()):
                rv["nicknames"].append(gma.persona.username)
                rv["ids"].append(gma.persona.id)

        emit('nicknames', rv, room=message["room_id"])


@socketio_authenticated_only
@socketio.on('text', namespace='/movements')
def text(message):
    """Sent by a client when the user entered a new message.
    The message is sent to all people in the room."""

    thought_created = datetime.datetime.utcnow()
    thought_id = uuid4().hex
    errors = ""
    author = current_user.active_persona
    parent_thought = None

    if len(message['msg']) == 0:
        errors += "You were about to say something?"

    if "map_id" not in message:
        errors += "No Mindset context given."
    else:
        map = Mindset.query.get(message["map_id"])

    if message["parent_id"]:
        parent_thought = Thought.query.get(message["parent_id"])
        if parent_thought is None:
            errors += "Could not find the message before yours. "

    if errors == "":
        thought = Thought(
            id=thought_id,
            text=message['msg'],
            author=author,
            parent=parent_thought,
            created=thought_created,
            modified=thought_created,
            mindset_id=map.id)
        db.session.add(thought)

        text, planets = process_attachments(thought.text)
        thought.text = text

        for planet in planets:
            db.session.add(planet)

            if isinstance(planet, Mention):
                notification = MentionNotification(planet,
                    author, url_for('web.thought', id=thought_id))
                send_external_notifications(notification)
                db.session.add(notification)

            assoc = PlanetAssociation(thought=thought, planet=planet, author=author)
            thought.planet_assocs.append(assoc)
            app.logger.info("Attached {} to new {}".format(planet, thought))
            db.session.add(assoc)

        if parent_thought:
            notif = ReplyNotification(parent_thought=parent_thought, author=author,
                url=url_for('web.thought', id=thought_id))
            send_external_notifications(notif)
            db.session.add(notif)

        try:
            db.session.commit()
        except SQLAlchemyError, e:
            db.session.rollback()
            app.logger.error("Error adding to chat mindset: {}".format(e))
            errors += "An error occured saving your message. Please try again. "
        else:
            app.logger.info(u"{} {}: {}".format(
                map, author.username, thought.text))

            # Render using templates
            chatline_template = current_app.jinja_env.get_template(
                'chatline.html')
            thought_macros_template = current_app.jinja_env.get_template(
                'macros/thought.html')
            thought_macros = thought_macros_template.make_module(
                {'request': request})

            data = {
                'username': author.username,
                'msg': chatline_template.render(thought=thought),
                'thought_id': thought.id,
                'parent_id': thought.parent_id,
                'parent_short': thought_macros.short(thought.parent) if thought.parent else None,
                'vote_count': thought.oneup_count()
            }
            emit('message', data, room=message["room_id"])

            reply_data = {
                'msg': thought_macros.comment(thought),
                'parent_id': thought.parent.id if thought.parent else None
            }
            emit('comment', reply_data, room=message["room_id"])

    if errors != "":
        app.logger.warning("Errors creating Thought: {}".format(errors))
        emit('error', errors)


@socketio_authenticated_only
@socketio.on('repost', namespace='/movements')
def repost(message):
    """Sent by client when the user reposts a Thought."""
    errors = ""
    author = current_user.active_persona

    if len(message['text']) == 0:
        errors += "You were about to say something?"

    map = Mindset.query.get(message["map_id"])

    if not message["parent_id"]:
        errors += "No repost source specified"
    else:
        parent_thought = Thought.query.get(message["parent_id"])
        if parent_thought is None:
            errors += "Could not find the original post. "

    if errors == "":
        thought = Thought.clone(parent_thought, author, map)
        thought.text = message['text']
        db.session.add(thought)

        mentions = find_mentions(thought.text)
        for mention_text, ident in mentions:
            if thought.planet_assocs.join(Mention).filter(Mention.text == mention_text).first() is None:
                app.logger.info("Adding new mention of {}".format(ident))
                mention = Mention(identity=ident, text=mention_text)
                notification = MentionNotification(
                    mention, author, url_for('web.thought', id=thought.id))
                send_external_notifications(notification)
                db.session.add(mention)
                db.session.add(notification)

        if parent_thought:
            notif = ReplyNotification(parent_thought=parent_thought, author=author,
                url=url_for('web.thought', id=thought.id))
            send_external_notifications(notif)
            db.session.add(notif)

        try:
            db.session.commit()
        except SQLAlchemyError, e:
            db.session.rollback()
            app.logger.error("Error completing Thought repost: {}".format(e))
            errors += "An error occured saving your message. Please try again. "
        else:
            app.logger.info(u"Repost {} {}: {}".format(
                map if map else "[no mindset]", author.username, thought.text))

            # Render using templates
            chatline_template = current_app.jinja_env.get_template(
                'chatline.html')
            thought_macros_template = current_app.jinja_env.get_template(
                'macros/thought.html')
            thought_macros = thought_macros_template.make_module(
                {'request': request})

            if map is not None:
                data = {
                    'username': author.username,
                    'msg': chatline_template.render(thought=thought),
                    'thought_id': thought.id,
                    'parent_id': thought.parent_id,
                    'parent_short': thought_macros.short(thought.parent),
                    'vote_count': thought.oneup_count()
                }
                emit('message', data, room=map.id)

            reply_data = {
                'msg': thought_macros.comment(thought),
                'parent_id': parent_thought.id
            }
            emit('comment', reply_data, room=message["room_id"])

    if errors != "":
        app.logger.warning("Errors creating Thought: {}".format(errors))
        emit('error', errors)

    return {
        "status": "success" if len(errors) == 0 else "error",
        "errors": errors,
        "message": "Thought was reposted to {}".format(map.name),
        "map_id": map.id if map else None,
        "thought_id": thought.id if thought else None,
        "url": url_for('web.thought', id=thought.id)
    }


@socketio_authenticated_only
@socketio.on('left', namespace='/movements')
def left(message):
    """Sent by clients when they leave a room.
    A status message is broadcast to all people in the room."""
    leave_room(message['room_id'])
    emit('status', {'msg': current_user.active_persona.username + ' has left the room.'}, room=message["room_id"])


@socketio_authenticated_only
@socketio.on('vote_request', namespace='/movements')
def vote_request(message):
    """
    Issue a vote to a Thought using the currently activated Persona

    Args:
        thought_id (string): ID of the Thought
    """
    error_message = ""
    thought_id = message.get('thought_id')
    thought = None

    if thought_id is None:
        error_message += "Vote event missing parameter. "

    if len(error_message) == 0:
        thought = Thought.query.get_or_404(thought_id)
        try:
            upvote = thought.toggle_oneup()
        except PersonaNotFoundError:
            error_message += "Please activate a Persona for voting. "
            upvote = None
        except UnauthorizedError:
            error_message += "You are not authorized to do this. Please login again."
            upvote = None

    data = dict()
    if len(error_message) > 0:
        app.logger.error("Error processing vote event from {} on {}: {}".format(current_user.active_persona, (thought or "<Thought {}>".format(thought_id or "with unknown id")), error_message))
        data = {
            "meta": {
                "error_message": error_message
            }
        }
    else:
        app.logger.debug("Processed vote by {} on {}".format(upvote.author, thought))
        data = {
            "votes": [{
                "thought_id": thought.id,
                "vote_count": thought.oneup_count(),
                "author_id": upvote.author_id
            }]
        }

        message_vote = {
            "author_id": upvote.author_id,
            "action": "insert" if len(upvote.vesicles) == 0 else "update",
            "object_id": upvote.id,
            "object_type": "Oneup",
            "recipients": thought.author.contacts.all() + [thought.author, ]
        }

        local_model_changed.send(upvote, message=message_vote)
        emit('vote', data, broadcast=True)


@socketio.on_error(namespace='/movements')
def chat_error_handler(e):
    app.logger.error('An error has occurred: ' + str(e))
