# -*- coding: utf-8 -*-
"""
    glia.events
    ~~~~~

    Socket.IO server for event handling

    :copyright: (c) 2015 by Vincent Ahrend.
"""

import functools

from datetime import datetime
from flask import request
from flask.ext.login import current_user
from flask.ext.socketio import emit, join_room, leave_room
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError

from . import app
from .. import socketio, db
from nucleus.nucleus.models import Starmap, Star


def socketio_authenticated_only(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated():
            request.namespace.disconnect()
        else:
            return f(*args, **kwargs)
    return wrapped


@socketio_authenticated_only
@socketio.on('joined', namespace='/groups')
def joined(message):
    """Sent by clients when they enter a room.
    A status message is broadcast to all people in the room."""
    if "room_id" not in message:
        message["room_id"] = "base"

    join_room(message["room_id"])
    app.logger.info("{} joined group chat {}".format(current_user.active_persona, message['room_id']))
    emit('status', {'msg': current_user.active_persona.username + ' has entered the room.'}, room=message["room_id"])
    emit('nicknames', [current_user.active_persona.username, ], room=message["room_id"])


@socketio_authenticated_only
@socketio.on('text', namespace='/groups')
def text(message):
    """Sent by a client when the user entered a new message.
    The message is sent to all people in the room."""

    star_created = datetime.utcnow()
    star_id = uuid4().hex
    errors = ""

    if len(message['msg']) == 0:
        errors += "Can't send empty message. "

    map = Starmap.query.get(message["room_id"])
    if map is None:
        errors += "Chat room could not be found. "

    star = Star(
        id=star_id,
        text=message['msg'],
        author=current_user.active_persona,
        created=star_created,
        modified=star_created)
    db.session.add(star)

    map.index.append(star)
    db.session.add(map)

    if errors == "":
        try:
            db.session.commit()
        except SQLAlchemyError, e:
            db.session.rollback()
            app.logger.error("Error adding to chat starmap: {}".format(e))
            errors += "An error occured saving your message. Please try again. "
        else:
            app.logger.info("{} {}: {}".format(map, current_user.active_persona.username, star.text))
            emit('message', {'msg': current_user.active_persona.username + ':' + message['msg']}, room=message["room_id"])

    if errors:
        emit('error', errors)


@socketio_authenticated_only
@socketio.on('left', namespace='/groups')
def left(message):
    """Sent by clients when they leave a room.
    A status message is broadcast to all people in the room."""
    leave_room(message['room_id'])
    emit('status', {'msg': current_user.active_persona.username + ' has left the room.'}, room=message["room_id"])


@socketio.on_error(namespace='/groups')
def chat_error_handler(e):
    app.logger.error('An error has occurred: ' + str(e))
