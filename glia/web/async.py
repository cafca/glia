# -*- coding: utf-8 -*-
"""
    glia.async
    ~~~~~

    Implements asynchronous views for web interface

    :copyright: (c) 2015 by Vincent Ahrend.
"""
from flask import render_template, url_for
from flask.ext.login import login_required

from . import app
from glia.web.dev_helpers import http_auth
from nucleus.nucleus.models import Star, Starmap


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
