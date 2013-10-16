# -*- coding: utf-8 -*-
"""
    glia.myelin
    ~~~~~

    Implements Myelin API.

    :copyright: (c) 2013 by Vincent Ahrend.
"""
@app.route('/myelin/v0/stars/', methods=["GET"])
def star_lookup():
    """Find star records"""
    pass


@app.route('/myelin/v0/stars/<star_id>/', methods=["GET", "PUT", "DELETE"])
def stars():
    """Access star records"""
    if request.method == "GET":
        pass
    elif request.method == "PUT":
        pass
    elif request.method == "DELETE":
        pass


@app.route('/myelin/v0/planets/', methods=["GET"])
def planet_lookup():
    """Find planet records"""
    pass


@app.route('/myelin/v0/planets/<planet_id>/', methods=["GET", "PUT", "DELETE"])
    """Access planet records"""
    if request.method == "GET":
        pass
    elif request.method == "PUT":
        pass
    elif request.method == "DELETE":
        pass