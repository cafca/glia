import datetime
import flask

from glia import app, db, ERROR
from glia.helpers import error_message, session_message, message_errors
from flask import request, jsonify
from models import Certificate, Notification, Persona


@app.route('/p/<persona_id>/create', methods=['POST'])
def create_persona(persona_id):
    # Validate request
    errors = message_errors(request.json)
    if errors:
        return error_message(errors)

    # Validate request data
    data = request.json['data']
    required_fields = [
        'persona_id', 'username', 'email_hash', 'sign_public', 'crypt_public', 'reply_to']
    errors = list()
    for field in required_fields:
        if field not in data:
            errors.append((4, "{} ({})".format(ERROR[4][1], field)))

    if errors:
        return error_message(errors=errors)

    p = Persona(
        persona_id=data["persona_id"],
        username=data["username"],
        sign_public=data["sign_public"],
        crypt_public=data["crypt_public"],
        email_hash=data["email_hash"],
        host=request.remote_addr,
        port=data["reply_to"],
    )
    p.reset()
    db.session.add(p)
    db.session.commit()

    app.logger.info("New persona {} registered from {}:{}".format(
        p.persona_id, p.host, p.port))

    data = {
        'timeout': p.timeout().isoformat(),
        'session_id': p.session_id,
        'errors': [],
    }
    return session_message(data=data)


@app.route('/find-people', methods=['POST'])
def find_people():
    # Validate request
    errors = message_errors(request.json)
    if errors:
        return error_message(errors)

    # Find corresponding personas
    # TODO: Allow multiple lookups at once
    email_hash = request.json['data']['email_hash']
    p = Persona.query.filter_by(email_hash=email_hash).first()

    if p:
        # Compile response
        app.logger.info("[find people] Persona {} found".format(p))
        data = {
            'found': p.export(include=[
                "persona_id",
                "username",
                "host",
                "port",
                "crypt_public",
                "sign_public",
                "connectable"]),
        }
    else:
        app.logger.info(
            "[find people] Persona <{}> not found.".format(email_hash[:8]))
        data = None

    return session_message(data=data)


@app.route('/', methods=['GET'])
def index():
    """Display debug information"""
    sessions = Persona.query.all()

    return flask.render_template("index.html", sessions=sessions)


@app.route('/p/<persona_id>/', methods=['GET', 'POST'])
def persona(persona_id):
    if request.method == 'GET':
        # keep-alive (and lookup)

        p = Persona.query.get(persona_id)

        if p is None:
            app.logger.error("Persona not found: {}".format(persona_id))
            return error_message(errors=[ERROR[3], ])

        if not p.is_valid():
            app.logger.info('Session invalid: {session}.'.format(
                session=p.session_id))

            data = {
                'errors': [ERROR[6], ],
                'auth': p.auth
            }
            return session_message(data=data)

        # Keep session alive
        p.last_connected = datetime.datetime.now()
        db.session.add(p)
        db.session.commit()

        # Compile notifications
        notifications = Notification.query.filter_by(
            recipient_id=persona_id).all()

        notification_json = list()
        for notif in notifications:
            notification_json.append(notif.message_json)

        data = {
            'timeout': p.timeout().isoformat(),
            'session_id': p.session_id,
            'notifications': notification_json
        }
        return session_message(data=data)

    elif request.method == 'POST':
        # Login

        errors = message_errors(request.json)
        if errors:
            return error_message(errors)

        data = request.json['data']
        required_fields = ['auth_signed']
        errors = list()
        for field in required_fields:
            if field not in data:
                errors.append((4, "{} ({})".format(ERROR[4][1], field)))
        if errors:
            return error_message(errors=errors)

        # Retrieve persona entry
        p = Persona.query.get(persona_id)
        if p is None:
            return error_message(errors=[ERROR[3], ])

        # Validate request auth
        is_valid = p.verify(p.auth, data['auth_signed'])
        if not is_valid:
            app.logger.error("Login failed with invalid signature.")
            return error_message(errors=[ERROR[5], ])

        # Create new session
        session_id = p.reset()
        p.last_connected = datetime.datetime.now()
        db.session.add(p)
        db.session.commit()

        data = {
            'timeout': p.timeout().isoformat(),
            'session_id': session_id,
            'errors': [],
        }
        return session_message(data=data)


@app.route('/peerinfo', methods=['POST'])
def peerinfo():
    """Return address for each of submitted peer IDs"""
    peer_info = dict()
    for p_id in request.json['request']:
        p = Persona.query.get(p_id)
        if p:
            print "{}: {}:{}".format(p.username, p.host, p.port)
            peer_info[p_id] = (p.host, p.port)

    app.logger.info("Sending peer info for {} addresses.".format(len(request.json)))

    return jsonify(peer_info)
