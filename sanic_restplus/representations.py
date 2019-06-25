# -*- coding: utf-8 -*-
try:
    from ujson import dumps
except ImportError:
    from json import dumps

from sanic.response import text

def output_json(request, data, code, headers=None):
    '''Makes a Flask response with a JSON encoded body'''
    current_app = request.app
    settings = current_app.config.get('RESTPLUS_JSON', {})

    # If we're in debug mode, and the indent is not set, we set it to a
    # reasonable value here.  Note that this won't override any existing value
    # that was set.
    if current_app.debug:
        settings.setdefault('indent', 4)

    # always end the json dumps with a new line
    # see https://github.com/mitsuhiko/flask/pull/1262
    dumped = dumps(data, **settings) + "\n"

    resp = text(dumped, code, content_type='application/json')
    resp.headers.update(headers or {})
    return resp
