# -*- coding: utf-8 -*-
"""
    glia.events
    ~~~~~

    Socket.IO server for event handling

    :copyright: (c) 2015 by Vincent Ahrend.
"""

import functools

from datetime import datetime
from flask import request, current_app
from flask.ext.login import current_user
from flask.ext.socketio import emit, join_room, leave_room
from flask.ext.misaka import markdown
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError
from hashlib import sha256

from . import app
from .. import socketio, db
from glia.web.helpers import find_links
from nucleus.nucleus.models import Starmap, Star, LinkPlanet, PlanetAssociation
from nucleus.nucleus import notification_signals, PersonaNotFoundError

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


@socketio_authenticated_only
@socketio.on('joined', namespace='/groups')
def joined(message):
    """Sent by clients when they enter a room.
    A status message is broadcast to all people in the room."""
    if not current_user.is_active():
        app.logger.info("Inactive users can't join chat")
    else:
        if "room_id" not in message:
            message["room_id"] = "base"

        join_room(message["room_id"])
        app.logger.info("{} joined group chat {}".format(current_user.active_persona, message['room_id']))
        emit('status', {'msg': current_user.active_persona.username + ' has entered the room.'}, room=message["room_id"])

        data = {'nicknames': [current_user.active_persona.username, ], 'ids': [current_user.active_persona.id, ]}
        emit('nicknames', data, room=message["room_id"])


@socketio_authenticated_only
@socketio.on('text', namespace='/groups')
def text(message):
    """Sent by a client when the user entered a new message.
    The message is sent to all people in the room."""

    star_created = datetime.utcnow()
    star_id = uuid4().hex
    errors = ""
    author = current_user.active_persona

    if len(message['msg']) == 0:
        errors += "Can't send empty message. "

    map = Starmap.query.get(message["room_id"])
    if map is None:
        errors += "Chat room could not be found. "

    # Extract links and replace in text
    links, text = find_links(message['msg'], app.logger)

    for link in links:
        emit('status', {'msg': 'Link found: {}'.format(link.url)})

    star = Star(
        id=star_id,
        text=text,
        author=author,
        created=star_created,
        modified=star_created)
    db.session.add(star)

    map.index.append(star)
    db.session.add(map)

    for link in links:
        planet = LinkPlanet.get_or_create(link.url)
        db.session.add(planet)

        assoc = PlanetAssociation(star=star, planet=planet, author=author)
        star.planet_assocs.append(assoc)
        app.logger.info("Attached {} to new {}".format(planet, star))
        db.session.add(assoc)

    if errors == "":
        try:
            db.session.commit()
        except SQLAlchemyError, e:
            db.session.rollback()
            app.logger.error("Error adding to chat starmap: {}".format(e))
            errors += "An error occured saving your message. Please try again. "
        else:
            app.logger.info("{} {}: {}".format(map, author.username, star.text))

            # Render using template
            template = current_app.jinja_env.get_template('chatline.html')
            data = {
                'username': author.username,
                'msg': template.render(star=star),
                'star_id': star.id,
                'vote_count': star.oneup_count()
            }
            emit('message', data, room=message["room_id"])

    if errors:
        emit('error', errors)


@socketio_authenticated_only
@socketio.on('left', namespace='/groups')
def left(message):
    """Sent by clients when they leave a room.
    A status message is broadcast to all people in the room."""
    leave_room(message['room_id'])
    emit('status', {'msg': current_user.active_persona.username + ' has left the room.'}, room=message["room_id"])


@socketio_authenticated_only
@socketio.on('vote_request', namespace='/groups')
def vote_request(message):
    """
    Issue a vote to a Star using the currently activated Persona

    Args:
        star_id (string): ID of the Star
    """
    error_message = ""
    star_id = message.get('star_id')
    star = None

    if star_id is None:
        error_message += "Vote event missing parameter. "

    if len(error_message) == 0:
        star = Star.query.get_or_404(star_id)
        try:
            upvote = star.toggle_oneup()
        except PersonaNotFoundError:
            error_message += "Please activate a Persona for voting. "
            upvote = None

    data = dict()
    if len(error_message) > 0:
        app.logger.error("Error processing vote event from {} on {}: {}".format(current_user.active_persona, (star or "<Star {}>".format(star_id or "with unknown id")), error_message))
        data = {
            "meta": {
                "error_message": error_message
            }
        }
    else:
        app.logger.debug("Processed vote by {} on {}".format(upvote.author, star))
        data = {
            "votes": [{
                "star_id": star.id,
                "vote_count": star.oneup_count(),
                "author_id": upvote.author_id
            }]
        }

        message_vote = {
            "author_id": upvote.author_id,
            "action": "insert" if len(upvote.vesicles) == 0 else "update",
            "object_id": upvote.id,
            "object_type": "Oneup",
            "recipients": star.author.contacts.all() + [star.author, ]
        }

        local_model_changed.send(upvote, message=message_vote)
        emit('vote', data, broadcast=True)


@socketio.on_error(namespace='/groups')
def chat_error_handler(e):
    app.logger.error('An error has occurred: ' + str(e))
