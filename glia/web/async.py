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


@app.route('/map/<starmap_id>', methods=["GET"])
@app.route('/map/<starmap_id>/backlog-<index_id>/', methods=["GET"])
@login_required
@http_auth.login_required
def backlog(starmap_id, index_id):
    from flask import jsonify
    errors = ""
    html = ""

    sm = Starmap.query.get(starmap_id)
    if sm is None:
        errors += "Error loading more items. Please refresh page. "

    index_star = Star.query.get(index_id)
    if index_star is None:
        errors += "Error loading more items. Please refresh page. "

    if len(errors) == 0:
        stars = sm.index.filter_by(state=0).filter(Star.created < index_star.created).order_by(Star.created.desc()).limit(51)[::-1]

        for star in stars[:50]:
            html = "\n".join([html, render_template('chatline.html', star=star)])

        end_reached = True if len(stars) < 51 else False

    if errors:
        return(errors)
    else:
        return(jsonify({
            'end_reached': end_reached,
            'html': html,
            'next_url': url_for('.backlog', starmap_id=starmap_id, index_id=stars[0].id),
        }))
