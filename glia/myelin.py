# -*- coding: utf-8 -*-
"""
    glia.myelin
    ~~~~~

    Implements Myelin API.

    :copyright: (c) 2013 by Vincent Ahrend.
"""

from glia import app
from glia.models import DBVesicle
from glia.views import error_message 
from nucleus import ERROR
from nucleus.vesicle import Vesicle

from flask import request, jsonify

@app.route('/v0/myelin/feed/<persona_id>/')
def feed(persona_id):
    """Return a feed of the most recent Vesicles sent to this Persona"""
    pass

@app.route('/v0/myelin/vesicles/<vesicle_id>/', methods=["GET", "PUT", "DELETE"])
def vesicle(vesicle_id):
    """Access star records"""
    if request.method == "GET":
        """Return the requested vesicle"""
        v = DBVesicle.query.get(vesicle_id)
        
        if v is None:
            app.logger.warning("Requested <Vesicle [{}]> could not be found".format(vesicle_id[:6]))
            return error_message([ERROR["OBJECT_NOT_FOUND"](vesicle_id)])
        else:
            return jsonify({
                "vesicles": [v.json, ]
            })

    elif request.method == "PUT":
        """Store the enclosed vesicle in the database"""
        
        # Validate request
        if "vesicles" not in request.json or not isinstance(request.json["vesicles"], list) or len(request.json["vesicles"]) == 0:
            app.logger.error("Malformed request: {}".format(request.json))
            return error_message([ERROR["MISSING_KEY"]("vesicles")])


        try:
            v_json = request.json["vesicles"][0]
            v = Vesicle.read(v_json)
        except ValueError, e:
            app.logger.error("Error loading vesicle JSON: {}".format(e))
            return error_message([ERROR["PROTOCOL_UNSUPPORTED"], ])
        except KeyError, e:
            app.logger.error("Missing key for loading vesicle JSON: {}".format(e))
            return error_message([ERROR["MISSING_KEY"](e)])

        # Store new Vesicle
        if v is not None:
            v.save()

        # TODO: Queue recipient notifications
        return jsonify({
            "vesicles": [v_json, ]
            })
