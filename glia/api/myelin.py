# -*- coding: utf-8 -*-
"""
    glia.myelin
    ~~~~~

    Implements Myelin API.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import iso8601

from flask import request, jsonify
from nucleus.nucleus import ERROR, InvalidSignatureError, PersonaNotFoundError
from nucleus.nucleus.models import Persona
from nucleus.nucleus.vesicle import Vesicle

from . import app
from .views import error_message

# Results returned per page
PER_PAGE = 50


def get_vesicle_or_error(vesicle_id):
    """
    Return a Vesicle in JSON format or an error message

    Parameters:
        vesicle_id (str): ID of the Vesicle to be returned

    Returns:
        Response object containing a JSON encoded dictionary. It has a key
        `vesicles` containing a list with the JSON encoded Vesicle as its value
    """
    v = Vesicle.query.get(vesicle_id)

    if v is None:
        app.logger.warning("Requested <Vesicle [{}]> could not be found".format(vesicle_id[:6]))
        return error_message([ERROR["OBJECT_NOT_FOUND"](vesicle_id)])
    else:
        return jsonify({
            "vesicles": [v.json, ]
        })


def store_vesicle_or_error(vesicle_json):
    """
    Store a vesicle in the database and return a JSON response

    Parameters:
        vesicle_json (str): JSON encoded Vesicle to be stored

    Returns:
        Response object containing a JSON encoded dictionary. It has a key
        `vesicles` containing a list with the stored Vesicle as its value
    """
    try:
        v = Vesicle.read(vesicle_json)
    except InvalidSignatureError, e:
        app.logger.error("Error loading vesicle: {}".format(e))
        return error_message([ERROR["INVALID_SIGNATURE"]])
    except PersonaNotFoundError, e:
        app.logger.error("Error loading vesicle: {}".format(e))
        return error_message([ERROR["OBJECT_NOT_FOUND"]("Author not found"), ])
    except ValueError, e:
        app.logger.error("Error loading vesicle JSON: {}".format(e))
        return error_message([ERROR["PROTOCOL_UNSUPPORTED"], ])
    except KeyError, e:
        app.logger.error("Missing key for loading vesicle JSON: {}".format(e))
        return error_message([ERROR["MISSING_KEY"](e)])

    # Store new Vesicle using the json generated by the sender
    v.save(vesicle_json=vesicle_json)

    app.logger.info("JSON\n{}".format(vesicle_json))

    # TODO: Queue recipient notifications
    return jsonify({
        "vesicles": [vesicle_json, ]
    })


@app.route('/v0/myelin/vesicles/<vesicle_id>/', methods=["GET", "PUT"])
def vesicles(vesicle_id):
    """Manage notification vesicles"""
    # Just return the vesicle for GET request
    if request.method == "GET":
        app.logger.info("Processing GET request for <Vesicle [{}]>".format(vesicle_id))
        return get_vesicle_or_error(vesicle_id)

    # For PUT request: store the enclosed vesicle in the database
    elif request.method == "PUT":
        app.logger.info("Processing PUT request for <Vesicle [{}]>".format(vesicle_id))
        # Validate request
        if (("vesicles" not in request.json) or
                (not isinstance(request.json["vesicles"], list)) or
                (len(request.json["vesicles"]) == 0)):
            app.logger.error("Malformed request: {}".format(request.json))
            return error_message([ERROR["MISSING_KEY"]("vesicles")])

        vesicle_json = request.json["vesicles"][0]
        return store_vesicle_or_error(vesicle_json)


@app.route('/v0/myelin/recipient/<recipient_id>/', methods=["GET"])
def recipient(recipient_id):
    """Return vesicles with a specific recipient"""
    # Validate and parse arguments
    recipient = Persona.query.get(recipient_id)
    if recipient is None:
        app.logger.warning("Request for unavailable Persona's Vesicle stream (ID: '{}'')".format(recipient_id))
        return error_message(ERROR["OBJECT_NOT_FOUND"]("<Persona [{}]>".format(recipient)))

    # Get inbox
    from sqlalchemy import asc
    inbox = recipient.inbox.order_by(asc(Vesicle.created))

    offset_string = request.args.get('offset')
    offset = None
    if offset_string is not None:
        try:
            offset = iso8601.parse_date(offset_string)
        except iso8601.ParseError, e:
            app.logger.error("Error parsing offset '{}' ({})".format(offset_string, e))
            return error_message([ERROR["INVALID_VALUE"]("Error parsing offset")])
        else:
            inbox = inbox.filter(Vesicle.modified > offset).order_by(Vesicle.modified)

    # Inbox is empty
    if inbox is None:
        resp = {"vesicles": [], }
    else:
        resp = dict(vesicles=list(), meta=dict(myelin_modified=dict()))
        for vesicle in inbox:
            resp["vesicles"].append(vesicle.json)
            resp["meta"]["myelin_modified"][vesicle.id] = vesicle.modified.isoformat()

    if len(resp["vesicles"]) > 0:
        app.logger.info("Returning {count} vesicles for {recipient}\n{filter}\n{listing}".format(
            count=len(resp["vesicles"]),
            recipient=recipient,
            filter="(Offset is {})".format(offset) if offset is not None else "(No offset)",
            listing="\n".join(["* ID:{} Modified:{} Recipients:{}".format(v.id, v.modified, len(v.recipients)) for v in inbox])
        ))
    return jsonify(resp)
