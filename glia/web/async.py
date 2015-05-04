# -*- coding: utf-8 -*-
"""
    glia.async
    ~~~~~

    Implements asynchronous views for web interface

    :copyright: (c) 2015 by Vincent Ahrend.
"""
from flask import render_template, url_for, jsonify
from flask.ext.login import login_required, current_user

from . import app
from glia.web.dev_helpers import http_auth
from nucleus.nucleus.database import db
from nucleus.nucleus.models import Star, Starmap, Group


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route('/async/chat/<starmap_id>', methods=["GET"])
@app.route('/async/chat/<starmap_id>/before-<index_id>/', methods=["GET"])
@login_required
@http_auth.login_required
def async_chat(starmap_id, index_id=None):
    from flask import jsonify
    errors = ""
    html = ""
    next_url = None

    sm = Starmap.query.get(starmap_id)
    if sm is None:
        errors += "Error loading more items. Please refresh page. "

    if index_id:
        index_star = Star.query.get(index_id)
        if index_star is None:
            errors += "Error loading more items. Please refresh page. "

    if len(errors) == 0:
        stars = sm.index.filter_by(state=0).order_by(Star.created.desc())

        if index_id:
            stars = stars.filter(Star.created < index_star.created)

        stars = stars.limit(51)[::-1]

        for star in stars[:50]:
            html = "\n".join([html, render_template('chatline.html', star=star)])

        end_reached = True if len(stars) < 51 else False

    if errors:
        return(jsonify({
            'html': errors,
            'next_url': None,
        }))
    else:
        if not end_reached:
            next_url = url_for('.async_chat', starmap_id=starmap_id, index_id=stars[0].id)
        return(jsonify({
            'end_reached': end_reached,
            'html': html,
            'next_url': next_url,
        }))


@app.route("/async/group/<group_id>/toggle_following", methods=["POST", "GET"])
@login_required
@http_auth.login_required
def async_toggle_group_following(group_id):
    group = Group.query.get(group_id)
    if group is None:
        raise InvalidUsage(message="Group not found", code=404)

    if not current_user or not current_user.active_persona:
        raise InvalidUsage(message="Activate a Persona to do this.")

    following = current_user.active_persona.toggle_following_group(group=group)

    db.session.add(current_user.active_persona)
    db.session.commit()

    rv = {
        "group_id": group.id,
        "persona_id": current_user.active_persona.id,
        "following": following
    }

    return jsonify(rv)


@app.route("/async/group/<group_id>/toggle_membership", methods=["POST", "GET"])
@login_required
@http_auth.login_required
def async_toggle_group_membership(group_id):
    group = Group.query.get(group_id)
    if group is None:
        raise InvalidUsage(message="Group not found", code=404)

    if not current_user or not current_user.active_persona:
        raise InvalidUsage(message="Activate a Persona to do this.")

    gms = current_user.active_persona.toggle_group_membership(group=group)
    if gms:
        rv = {
            "role": gms.role,
            "created": gms.created,
            "description": gms.description,
            "active": gms.active,
            "last_seen": gms.last_seen
        }
        db.session.add(gms)
    else:
        rv = None

    db.session.commit()

    return jsonify({
        "group_id": group.id,
        "persona_id": current_user.active_persona.id,
        "association": rv
    }, )