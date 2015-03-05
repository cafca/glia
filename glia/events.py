import functools

from flask import session, request
from flask.ext.login import current_user
from flask.ext.socketio import emit, join_room, leave_room

from glia import app, socketio


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
    room = session.get('room')
    join_room(room)
    emit('status', {'msg': session.get('name') + ' has entered the room.'}, room=room)


@socketio_authenticated_only
@socketio.on('text', namespace='/groups')
def text(message):
    """Sent by a client when the user entered a new message.
    The message is sent to all people in the room."""
    room = session.get('room')
    app.logger.debug("{}: {}".format(session.get('name'), message['msg']))
    emit('message', {'msg': session.get('name') + ':' + message['msg']}, room=room)


@socketio_authenticated_only
@socketio.on('left', namespace='/groups')
def left(message):
    """Sent by clients when they leave a room.
    A status message is broadcast to all people in the room."""
    room = session.get('room')
    leave_room(room)
    emit('status', {'msg': session.get('name') + ' has left the room.'}, room=room)


@socketio.on_error(namespace='/groups')
def chat_error_handler(e):
    print('An error has occurred: ' + str(e))
