# -*- coding: utf-8 -*-
"""
    glia.views
    ~~~~~

    Implements public Glia API.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
import datetime
import iso8601
import re

from flask import request, jsonify, abort, redirect, current_app
from sqlalchemy import func

from nucleus.nucleus.models import Persona, Souma, Movement
from nucleus.nucleus.vesicle import Vesicle
from nucleus.nucleus import ERROR

from nucleus.nucleus.connections import db

from . import app


def error_message(errors):
    """
    Construct a response containing the given error messages

    Args:
        errors (list): List of elements from nucleus.ERROR

    Returns:
        JSON-formatted response object
    """
    return jsonify({"meta": {"errors": errors}})


def valid_souma(souma_id):
    """Return True if souma_id is registered and not blocked

    Args:
        souma_id: 32 byte Souma ID

    Raises:
        ValueError: If Souma is None
        KeyError: If Souma is not found
    """
    if souma_id is None:
        raise ValueError("Souma ID can't be None")

    souma = Souma.query.get(souma_id)

    if souma is None:
        raise KeyError("Souma '{} was not found".format(souma_id))

    return True


@app.before_request
def authenticate():
    """Validate request has secure connection and valid souma"""

    # Match API requests
    rx = "/v0/"
    if re.match(rx, request.path):
        # HTTPS requests are not visible as such from within Heroku. Instead, the HTTP_X_FORWARDED_PROTO
        # header is set to 'https'
        if not any([current_app.config["DEBUG"] is True, request.headers.get("X-Forwarded-Proto", default=None) == 'https']):
                url = request.url
                secure_url = url.replace("http://", "https://")
                app.logger.debug("Redirecting from {} to {}".format(url, secure_url))
                return redirect(secure_url, code=301)

        if (request.path == '/v0/soumas/' and request.method == "POST"):
            # Allowed to access this resource without known souma id
            pass
        else:
            souma_id = request.headers.get("Glia-Souma", default="")
            souma = Souma.query.get(souma_id)
            if souma is None:
                app.logger.warning("Authentication failed: Souma {} not found.".format(souma_id))
                rsp = error_message([ERROR["SOUMA_NOT_FOUND"](souma_id)])
                rsp.status = "401 Souma {} not found.".format(souma_id)
                return rsp

            try:
                souma.authentic_request(request)
            except ValueError as e:
                app.logger.warning("Request failed authentication: {}\n{}".format(request, e))
                if app.config["AUTH_ENABLED"]:
                    abort(401)


@app.route('/v0/', methods=["GET"])
def index():
    """
    Return server status.
    """
    # TODO: Read server status
    # https://github.com/ciex/glia/issues/24
    server_status = (0, "OK")

    # TODO: Count online Soumas
    soumas_online = -1
    personas_registered = db.session.query(func.count(Persona.id)).first()[0]

    vesicles_stored = db.session.query(func.count(Vesicle.id)).first()[0]

    resp = {
        "server_status": [{
            "id": 0,
            "status_code": server_status[0],
            "status_message": server_status[1],
            "read_enabled": True,
            "write_enabled": True,
            "soumas_online": soumas_online,
            "personas_registered": personas_registered,
            "vesicles_stored": vesicles_stored,
        }]
    }

    return jsonify(resp)


@app.route('/v0/personas/', methods=["POST"])
def find_personas():
    """
    Find personas by hashed email address
    """

    if "email_hash" not in request.json or not isinstance(request.json["email_hash"], list):
        app.logger.error("Received malformed request for find_persona")
        return error_message([ERROR["MISSING_KEY"]('email_hash')])

    email_hash = request.json["email_hash"][0]

    # TODO: Verify correct hash format

    # Find corresponding personas
    result = Persona.query.filter_by(email=email_hash).all()

    resp = {'personas': list()}
    if result:
        # Compile response
        app.logger.debug("{} Personas found for email-hash {}".format(len(result), email_hash[:8]))
        for p in result:
            p_dict = p.export(include=[
                "id",
                "username",
                "modified",
                "crypt_public",
                "sign_public"])
            p_dict["email_hash"] = email_hash
            resp['personas'].append(p_dict)
    else:
        resp["meta"] = {"errors": [ERROR["OBJECT_NOT_FOUND"](email_hash), ]}
        app.logger.debug(
            "Persona <{}> not found.".format(email_hash[:8]))

    return jsonify(resp)


@app.route('/v0/personas/<persona_id>/', methods=["GET", "PUT", "DELETE"])
def personas(persona_id):
    """Access and modify persona records on the server"""

    if request.method == "GET":
        # Return persona info
        p = Persona.query.get(persona_id)
        resp = dict()
        if p:
            resp["personas"] = list()
            resp["personas"].append(p.export(include=[
                "id",
                "username",
                "modified",
                "crypt_public",
                "sign_public",
                "auth"]))
        else:
            resp["meta"] = dict()
            resp["meta"]["errors"] = [ERROR["OBJECT_NOT_FOUND"](persona_id), ]

        return jsonify(resp)

    elif request.method == "PUT":
        # Store new persona record on server

        # Validate request data
        if "personas" not in request.json or not isinstance(request.json["personas"], list):
            app.logger.error("Malformed request: {}".format(request.json))
            return error_message([ERROR["MISSING_KEY"]("personas")])

        new_persona = request.json['personas'][0]

        # Check required fields
        required_fields = [
            'persona_id', 'username', 'email_hash', 'sign_public', 'crypt_public', "modified"]
        errors = list()
        for field in required_fields:
            if field not in new_persona:
                errors.append(ERROR["MISSING_KEY"](field))

        # Check for duplicate identifier
        if "persona_id" in new_persona:
            p_existing = Persona.query.get(new_persona["persona_id"])
            if p_existing:
                errors.append(ERROR["DUPLICATE_ID"](new_persona["persona_id"]))

        # Parse 'modified' datetime
        try:
            modified = iso8601.parse_date(new_persona["modified"])
        except ValueError:
            errors.append(ERROR["INVALID_VALUE"](
                "'modified': {}".format(new_persona["modified"])))

        # Return in case of errors
        if errors:
            return error_message(errors)

        # Register new persona
        p = Persona(
            id=new_persona["persona_id"],
            username=new_persona["username"],
            modified=modified,
            sign_public=new_persona["sign_public"],
            crypt_public=new_persona["crypt_public"],
            email=new_persona["email_hash"],
        )
        p.reset()
        db.session.add(p)
        db.session.commit()

        app.logger.info("New {} registered".format(p))

        return jsonify({
            "sessions": [{
                "id": p.session_id,
                "timeout": p.timeout().isoformat()
            }]
        })

    elif request.method == "DELETE":
        pass


@app.route('/v0/movements/', methods=["GET", "POST"])
def find_movements():
    """Return top movements or movement search results

    The 'POST'-method expects a JSON formatted request body with a key 'query'
    containing a search term at least three characters long.
    """

    errors = list()
    results = None

    if request.method == "GET":
        # ------------------------
        # --- Retrieve top movements

        app.logger.info("Returning top movements")

        results = Movement.query.limit(10).all()

    elif request.method == "POST":
        # ------------------------
        # --- Validate query

        if "query" not in request.json or len(request.json['query']) == 0:
            errors.append(ERROR["MISSING_PARAMETER"]("search query"))
            app.logger.warning("Movement search request missing query parameter")

        query = request.json['query'][0]

        if not isinstance(query, basestring) or len(query) < 3:
            errors.append(ERROR["INVALID_VALUE"]("search query too short"))
            app.logger.info("Movement search query too short (was '{}')".format(query))

        else:
            app.logger.info("Movement search request for query '{}'".format(query))

            if query == "null":
                query = None

            # ------------------------
            # --- Retrieve results

            results = Movement.query.filter(Movement.username.like("%{}%".format(query))).all()

    # ------------------------
    # --- Compile return value

    if errors:
        return jsonify({"meta": {"errors": errors}})
    else:
        results = [result.export() for result in results]
        return jsonify({"movements": results})


@app.route('/v0/movements/<movement_id>/', methods=["GET", "PUT"])
def movements(movement_id):
    """Access and modify movement records on the server"""

    if request.method == "GET":
        # Return movement info
        mvmnt = Movement.query.get(movement_id)
        resp = dict()
        if mvmnt:
            resp["movements"] = list()
            resp["movements"].append(mvmnt.export(include=[
                "id",
                "username",
                "description",
                "created",
                "admin_id"]))
        else:
            resp["meta"] = dict()
            resp["meta"]["errors"] = [ERROR["OBJECT_NOT_FOUND"](movement_id), ]

        return jsonify(resp)

    elif request.method == "PUT":
        # Store new movement record on server

        # Validate request data
        if "movements" not in request.json or not isinstance(request.json["movements"], list):
            app.logger.error("Malformed request: {}".format(request.json))
            return error_message([ERROR["MISSING_KEY"]("movements")])

        movement = request.json['movements'][0]

        # Check required fields
        required_fields = [
            'movement_id', 'username', 'description', 'admin_id']
        errors = list()
        for field in required_fields:
            if field not in movement:
                errors.append(ERROR["MISSING_KEY"](field))

        # Check for duplicate identifier
        if "movement_id" in movement:
            m_existing = Movement.query.get(movement["movement_id"])
            if m_existing:
                errors.append(ERROR["DUPLICATE_ID"](movement["movement_id"]))

        # Retrieve admin record
        admin = Persona.query.get(movement["admin_id"])
        if admin is None:
            errors.append(ERROR["DUPLICATE_ID"](movement["admin_id"]))

        # Return in case of errors
        if errors:
            return error_message(errors)

        # Register new movement
        m = Movement(
            id=movement["movement_id"],
            username=movement["username"],
            description=movement["description"],
            admin=admin,
        )
        db.session.add(g)
        db.session.commit()

        app.logger.info("New movement '{}' registered".format(m.username.encode('utf-8')))

        return jsonify({
            "movements": [{
                "id": m.id,
                "username": m.username,
                "description": m.description,
                "created": m.created.isoformat()
            }]
        })


@app.route('/v0/sessions/', methods=["GET", "POST"])
def session_lookup():
    """Peer lookup"""
    if request.method == "GET":
        # Find by ID
        if "ids" in request.args:
            ids = request.args["ids"].split(",")
        else:
            app.logger.warning("Received malformed peer lookup request. Missing `ids` parameter.")
            return error_message([ERROR["MISSING_PARAMETER"]('ids')])

        resp = {"sessions": list()}
        found = 0
        for p_id in ids:
            p = Persona.query.get(p_id)
            resp["sessions"].append({
                "id": p_id,
                "soumas": [{
                    "host": None,
                    "port": None
                }]
            })
            if p:
                found += 1

        app.logger.info("Sending peer info for {}/{} addresses.\n* {}".format(
            found,
            len(ids),
            "\n* ".join(["{}: {}".format(s["id"], s["soumas"]) for s in resp["sessions"]])))
        return jsonify(resp)

    elif request.method == "POST":
        # Login

        # Validate request
        errors = list()
        try:
            data = request.json['personas'][0]
        except KeyError, e:
            app.logger.warning("Received malformed request: Missing key `e`".format(e))
            errors.append(ERROR["MISSING_KEY"](e))
            return error_message(errors)

        required_fields = ['auth_signed', 'id', 'reply_to']
        for field in required_fields:
            if field not in data:
                errors.append(ERROR["MISSING_KEY"](field))
        if errors:
            app.logger.warning("Received malformed request: Missing keys")
            return error_message(errors)

        # Retrieve persona entry
        p = Persona.query.get(data["id"])
        if p is None:
            return error_message([ERROR[3], ])

        # Validate request auth
        is_valid = p.verify(p.auth, data['auth_signed'])
        if not is_valid:
            app.logger.error("Login failed with invalid signature.")
            return error_message([ERROR[5], ])

        # Create new session
        session_id = p.reset()
        p.last_connected = datetime.datetime.now()
        db.session.add(p)
        db.session.commit()

        resp = {
            'sessions': [{
                'id': session_id,
                'timeout': p.timeout().isoformat(),
            }]
        }
        return jsonify(resp)


@app.route('/v0/sessions/<session_id>/', methods=["GET", "DELETE"])
def sessions(session_id):
    """Perform operations on login sessions"""
    if request.method == "GET":
        # keep-alive

        p = Persona.query.filter_by(session_id=session_id).first()

        if p is None:
            app.logger.error("No persona found with session {}".format(session_id))
            return error_message([ERROR["OBJECT_NOT_FOUND"]("persona"), ])

        if not p.is_valid():
            app.logger.info('Session invalid: {session}.'.format(
                session=p.session_id))

            resp = {
                'meta': {
                    'errors': [ERROR["INVALID_SESSION"], ],
                    'auth': p.auth
                }
            }
            return jsonify(resp)
        else:
            # Keep session alive
            app.logger.info("Successful keep-alive for {}".format(p))
            p.last_connected = datetime.datetime.now()
            db.session.add(p)
            db.session.commit()

            resp = {
                'sessions': [{
                    'id': p.session_id,
                    'timeout': p.timeout().isoformat(),
                }, ]
            }
            return jsonify(resp)
    elif request.method == "DELETE":
        pass


@app.route('/v0/soumas/', methods=["POST"])
def soumas():
    """
    Register a new Souma with this Glia
    """
    # Validate request
    resp = {"meta": {"errors": list()}}

    if not "soumas" in request.json or not isinstance(request.json["soumas"], list):
        resp["meta"]["errors"].append(ERROR["MISSING_PAYLOAD"])
        return jsonify(resp), 400
    new_souma = request.json["soumas"][0]

    required_fields = ["id", "crypt_public", "sign_public"]
    for f in required_fields:
        if f not in new_souma:
            resp["meta"]["errors"].append(ERROR["MISSING_KEY"](f))

    if "id" in new_souma:
        old_souma = Souma.query.get(new_souma["id"])
        if old_souma:
            resp["meta"]["errors"].append(ERROR["DUPLICATE_ID"](new_souma["id"]))

    if len(resp["meta"]["errors"]) == 0:
        souma = Souma(
            id=new_souma["id"],
            crypt_private=new_souma["crypt_public"],
            sign_public=new_souma["sign_public"])

        try:
            souma.authentic_request(request)
        except ValueError as e:
            app.logger.warning("Error registering new Souma {}\n{}".format(souma, e))
            resp["meta"]["errors"].append(ERROR["INVALID_SIGNATURE"])
        else:
            db.session.add(souma)
            db.session.commit()
            app.logger.info("Registered new {}".format(souma))

    return jsonify(resp)


@app.route('/v0/soumas/<souma_id>', methods=["GET"])
def souma_info(souma_id):
    """
    Return an info dict for a souma_id
    """
    s = Souma.query.get(souma_id)
    if s is not None:
        souma_info = s.export(include=["id", "crypt_public", "sign_public"])
        return jsonify({"soumas": [souma_info, ]})
    else:
        return error_message([ERROR["OBJECT_NOT_FOUND"](souma_id)])
