import functools
import re

from flask import session, request
from flask.ext.login import current_user
from flask.ext.socketio import emit, join_room, leave_room

from . import app
from .. import socketio
from glia.models import Group


def socketio_authenticated_only(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated():
            request.namespace.disconnect()
        else:
            return f(*args, **kwargs)
    return wrapped


def get_group_from_path(path):
    rx = "/groups/(.{32})"
    rx_match = re.match(rx, path)
    if rx_match:
        group_id = rx_match.group(1)
        rv = Group.query.get(group_id)
    else:
        rv = None
    return rv


@socketio_authenticated_only
@socketio.on('joined', namespace='/groups')
def joined(message):
    """Sent by clients when they enter a room.
    A status message is broadcast to all people in the room."""
    join_room(message['path'])
    emit('status', {'msg': session.get('name') + ' has entered the room.'}, room=message['path'])


@socketio_authenticated_only
@socketio.on('text', namespace='/groups')
def text(message):
    """Sent by a client when the user entered a new message.
    The message is sent to all people in the room."""
    app.logger.debug("{} {}: {}".format(message['path'], session.get('name'), message['msg']))
    emit('message', {'msg': session.get('name') + ':' + message['msg']}, room=message['path'])


@socketio_authenticated_only
@socketio.on('left', namespace='/groups')
def left(message):
    """Sent by clients when they leave a room.
    A status message is broadcast to all people in the room."""
    leave_room(message['path'])
    emit('status', {'msg': session.get('name') + ' has left the room.'}, room=message['path'])


@socketio.on_error(namespace='/groups')
def chat_error_handler(e):
    print('An error has occurred: ' + str(e))
