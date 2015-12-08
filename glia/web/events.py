# -*- coding: utf-8 -*-
"""
    glia.events
    ~~~~~

    Socket.IO server for event handling

    :copyright: (c) 2015 by Vincent Ahrend.
"""

import datetime
import functools
import traceback
import sys

from flask import request, current_app, url_for
from flask.ext.login import current_user
from flask.ext.socketio import emit, join_room, leave_room
from sqlalchemy.exc import SQLAlchemyError

from . import app
from .. import socketio, db
from glia.web.helpers import send_external_notifications
from nucleus.nucleus.helpers import find_mentions
from nucleus.nucleus.models import Mindset, Thought, Movement, \
    Persona, Mention, MentionNotification, ReplyNotification, Mindspace
from nucleus.nucleus import notification_signals, PersonaNotFoundError, \
    UnauthorizedError

# Create blinker signal namespace
local_model_changed = notification_signals.signal('local-model-changed')
movement_chat = notification_signals.signal('movement-chat')


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
    if not current_user.is_anonymous():
        request.namespace.join_room(current_user.active_persona.id)


#
# MOVEMENT WEBSOCKET
#


@movement_chat.connect
def movement_chat_relay(sender, **data):
    if not data.get("room_id"):
        raise ValueError("Invalid messaging channel")
    if not data.get("message"):
        raise ValueError("Missing message")

    print sender, data
    socketio.emit('status', {"msg": data.get('message')},
        room=data.get("room_id"), namespace="/movements")


@socketio.on_error(namespace='/movements')
def chat_error_handler(e):
    app.logger.error('An error has occurred: ' + str(e))
    traceback.print_exc(file=sys.stderr)


@socketio_authenticated_only
@socketio.on('joined', namespace='/movements')
def joined(message):
    """Sent by clients when they enter a room.
    A status message is broadcast to all people in the room."""
    if not current_user.is_active():
        app.logger.debug("Inactive users can't join chat")
    else:
        if "room_id" not in message:
            message["room_id"] = "base"

        current_user.active_persona.last_connected = datetime.datetime.utcnow()
        db.session.add(current_user.active_persona)
        db.session.commit()

        join_room(message["room_id"])
        app.logger.debug("{} joined movement chat {}".format(current_user.active_persona, message['room_id']))
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
@socketio.on('left', namespace='/movements')
def left(message):
    """Sent by clients when they leave a room.
    A status message is broadcast to all people in the room."""
    leave_room(message['room_id'])
    emit('status', {'msg': current_user.active_persona.username + ' has left the room.'}, room=message["room_id"])


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

        # Check if there were new mentions added to the Thought
        mentions = find_mentions(thought.text)
        for mention_text, ident in mentions:
            if thought.percept_assocs.join(Mention).filter(Mention.text == mention_text).first() is None:
                app.logger.info("Adding new mention of {}".format(ident))
                mention = Mention(identity=ident, text=mention_text)
                notification = MentionNotification(
                    mention, author, url_for('web.thought', id=thought.id))
                send_external_notifications(notification)
                db.session.add(mention)
                db.session.add(notification)

        parent_thought.update_comment_count(1)

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
                    'vote_count': thought.upvote_count()
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
@socketio.on('text', namespace='/movements')
def text(message):
    """Sent by a client when the user entered a new message.
    The message is sent to all people in the room."""

    errors = ""
    parent = None

    if len(message['msg']) == 0:
        errors += "You were about to say something?"

    if "parent_id" in message:
        parent = Thought.query.get(message["parent_id"])
        if parent is None:
            errors += "Could not find the message before yours. "

    if "map_id" not in message:
        if parent is None:
            errors += "New thoughts needs either a parent or a mindset to live in. "
        else:
            map = parent.mindset
    else:
        map = Mindset.query.get(message["map_id"])

    if errors == "":
        thought_data = Thought.create_from_input(
            text=message["msg"],
            mindset=map,
            parent=parent)
        thought = thought_data["instance"]
        thought.posted_from = "web-websocket"

        db.session.add(thought)

        try:
            db.session.commit()
        except SQLAlchemyError, e:
            db.session.rollback()
            app.logger.error("Error adding to chat mindset: {}".format(e))
            errors += "An error occured saving your message. Please try again. "
        else:
            app.logger.info(u"{} {}: {}".format(
                map, thought.author.username, thought.text))

            for notification in thought_data["notifications"]:
                send_external_notifications(notification)

            # Render using templates
            chatline_template = current_app.jinja_env.get_template(
                'chatline.html')
            thought_macros_template = current_app.jinja_env.get_template(
                'macros/thought.html')
            thought_macros = thought_macros_template.make_module(
                {'request': request})

            data = {
                'username': thought.author.username,
                'msg': chatline_template.render(thought=thought),
                'thought_id': thought.id,
                'parent_id': thought.parent_id,
                'parent_short': thought_macros.short(thought.parent) if thought.parent else None,
                'vote_count': thought.upvote_count()
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
            upvote = thought.toggle_upvote()
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

        if isinstance(thought.mindset, Mindspace) \
                and isinstance(thought.mindset.author, Movement):
            data["votes"][0]["voting_done"] = \
                thought.mindset.author.voting_done(thought)
