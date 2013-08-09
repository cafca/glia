# -*- coding: utf-8 -*-
"""
    glia.helpers
    ~~~~~

    Helper methods to encapsulate often used procedures

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import datetime
import flask

from glia import app, ERROR
from glia.models import Persona


def session_message(data):
    """Return session message containing `data`"""

    app.logger.debug("Sending session message ({})".format(
        flask.json.dumps(data)))

    #sig = SERVER_KEY.Sign(data)

    return flask.jsonify(
        data=data,
        message_type='session',
        #signature=sig,
        timestamp=datetime.datetime.now().isoformat(),
    )


def error_message(errors):
    """Create error response"""
    app.logger.warning('{errors}'.format(
        errors="\n".join(["{}: {}".format(e[0], e[1]) for e in errors])))

    data = {
        'errors': errors,
        'timestamp': datetime.datetime.now().isoformat()
    }
    #sig = SERVER_KEY.Sign(data)

    return flask.jsonify(
        data=data,
        message_type='error',
        #signature=sig,
        timestamp=datetime.datetime.now().isoformat(),
    )


def message_errors(message):
    """Validate message"""

    errors = list()
    if 'message_type' not in message:
        errors.append(ERROR[1])
    if 'data' not in message or 'data' is None:
        errors.append(ERROR[2])
    if 'signature' in message:
        author = Persona.query.get(message['author_id'])
        if author:
            if author.verify(message['data'], message['signature']):
                app.logger.info("Correct signature on {} from {}".format(
                    message['message_type'], author))
            else:
                app.logger.error("Invalid signature on {}".format(message))
                errors.append(ERROR[5])
        else:
            app.logger.error("Could not verify signature. Missing author. [{}]".format(message))

    return errors
