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

from glia import app, db
from flask import request, jsonify, abort, redirect, render_template, flash, url_for
from flask.ext.login import login_user, logout_user, login_required, current_user
from sqlalchemy import func
from uuid import uuid4

from models import Persona, Souma, DBVesicle, User, Group, Association
from forms import LoginForm, SignupForm, CreateGroupForm
from nucleus import ERROR


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
        if not any([app.config["DEBUG"] is True, request.headers.get("X-Forwarded-Proto", default=None) == 'https']):
                url = request.url
                secure_url = url.replace("http://", "https://")
                app.logger.info("Redirecting from {} to {}".format(url, secure_url))
                return redirect(secure_url, code=301)

        if (request.path == '/v0/soumas/' and request.method == "POST"):
            # Allowed to access this resource without known souma id
            pass
        else:
            souma_id = request.headers.get("Glia-Souma", default="")
            souma = Souma.query.get(souma_id)
            if souma is None:
                app.logger.info("Authentication failed: Souma {} not found.".format(souma_id))
                rsp = error_message([ERROR["SOUMA_NOT_FOUND"](souma_id)])
                rsp.status = "401 Souma {} not found.".format(souma_id)
                return rsp

            try:
                souma.authentic_request(request)
            except ValueError as e:
                app.logger.warning("Request failed authentication: {}\n{}".format(request, e))
                if app.config["AUTH_ENABLED"]:
                    abort(401)


@login_required
@app.route('/', methods=["GET"])
def index():
    """Front page"""
    groupform = CreateGroupForm()
    groups = Group.query.all()

    return render_template('index.html', groupform=groupform, groups=groups)


@login_required
@app.route('/groups/', methods=["GET", "POST"])
def groups():
    """Create groups"""
    form = CreateGroupForm()

    # Create a group
    if form.validate_on_submit():
        group_id = uuid4().hex
        group = Group(
            id=group_id,
            username=form.name.data,
            admin=current_user.active_persona)
        db.session.add(group)
        db.session.commit()
        flash("Your new group is ready!")
        return redirect(url_for('group', id=group_id))

    return render_template("groups.html", form=form)


@app.route('/groups/<id>', methods=["GET"])
def group(id):
    """Display a group's profile"""
    group = Group.query.get(id)
    if not group:
        flash("Group not found")
        return(redirect(url_for('groups')))
    return render_template('group.html', group=group)


@app.route('/stars/', methods=["POST"])
def create_star():
    """Post a new Star"""
    pass


@app.route('/login', methods=["GET", "POST"])
def login():
    """Login a user"""
    form = LoginForm()
    if form.validate_on_submit():
        app.logger.debug("Form validated fine")
        form.user.authenticated = True
        db.session.add(form.user)
        db.session.commit()
        login_user(form.user, remember=True)
        flash("Welcome back, {}".format(form.user.active_persona.username))
        return form.redirect(url_for('index'))
    elif request.method == "POST":
        app.logger.error("Invalid password")
        form.password.errors.append("Invalid password.")
    return render_template('login.html', form=form)


@login_required
@app.route('/logout', methods=["GET", "POST"])
def logout():
    """Logout a user"""
    user = current_user
    user.authenticated = False
    db.session.add(user)
    db.session.commit()
    logout_user()
    return redirect(url_for('index'))


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Signup a new user"""
    from uuid import uuid4
    form = SignupForm()

    if form.validate_on_submit():
        created_dt = datetime.datetime.utcnow()
        user = User(
            email=form.email.data,
            created=created_dt,
            modified=created_dt)
        user.set_password(form.password.data)
        db.session.add(user)

        created_dt = datetime.datetime.utcnow()
        persona = Persona(
            id=uuid4().hex,
            username=form.username.data,
            created=created_dt,
            modified=created_dt)

        db.session.add(persona)

        ap = user.active_persona
        if ap:
            ap.association[0].active = False

        association = Association(user=user, persona=persona, active=True)
        db.session.add(association)
        db.session.commit()

        login_user(user, remember=True)

        flash("Hello {}, you now have your own RKTIK account!".format(form.username.data))

        return form.redirect(url_for('index'))
    return render_template('signup.html', form=form)


@app.route('/v0/', methods=["GET"])
def api_index():
    """
    Return server status.
    """
    # TODO: Read server status
    # https://github.com/ciex/glia/issues/24
    server_status = (0, "OK")

    # TODO: Count online Soumas
    soumas_online = -1
    personas_registered = db.session.query(func.count(Persona.id)).first()[0]

    vesicles_stored = db.session.query(func.count(DBVesicle.id)).first()[0]

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
    result = Persona.query.filter_by(email_hash=email_hash).all()

    resp = {'personas': list()}
    if result:
        # Compile response
        app.logger.info("{} Personas found for email-hash {}".format(len(result), email_hash[:8]))
        for p in result:
            p_dict = p.export(include=[
                "id",
                "username",
                "modified",
                "host",
                "port",
                "crypt_public",
                "sign_public",
                "connectable"])
            p_dict["email_hash"] = email_hash
            resp['personas'].append(p_dict)
    else:
        resp["meta"] = {"errors": [ERROR["OBJECT_NOT_FOUND"](email_hash), ]}
        app.logger.info(
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
                "host",
                "port",
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
            email_hash=new_persona["email_hash"],
            host=request.remote_addr,
            port=new_persona["reply_to"],
        )
        p.reset()
        db.session.add(p)
        db.session.commit()

        app.logger.info("New {} registered from {}:{}".format(
            p, p.host, p.port))

        return jsonify({
            "sessions": [{
                "id": p.session_id,
                "timeout": p.timeout().isoformat()
            }]
        })

    elif request.method == "DELETE":
        pass


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
                    "host": p.host if p else None,
                    "port": p.port if p else None
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
        p.host = request.remote_addr
        p.port = data['reply_to']
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
            app.logger.info("Registered new {}".format(souma))
            db.session.add(souma)
            db.session.commit()

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
