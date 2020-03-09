# -*- coding: utf-8 -*-
import collections

from sanic_restplus._http import HTTPStatus

try:
    from orjson import dumps as fast_dumps, OPT_NON_STR_KEYS, OPT_NAIVE_UTC, OPT_UTC_Z

    has_orjson = True
    has_ujson = False
except ImportError:
    has_orjson = False
    try:
        from ujson import dumps as fast_dumps
        has_ujson = True
    except ImportError:
        has_ujson = False

from json import dumps


from sanic.response import text, HTTPResponse

def output_json_pretty(request, data, code, headers=None):
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

    resp = text(dumped, code, headers, content_type='application/json')
    return resp


if has_ujson:
    def output_json_fast_ujson(request, data, code, headers=None):
        current_app = request.app
        if current_app.debug:
            return output_json_pretty(request, data, code, headers=headers)
        settings = current_app.config.get('RESTPLUS_JSON', {})
        dumped = fast_dumps(data, **settings) + "\n"
        resp = text(dumped, code, headers, content_type='application/json')
        return resp
    output_json_fast = output_json_fast_ujson
elif has_orjson:
    #orjson_opts = OPT_NON_STR_KEYS | OPT_NAIVE_UTC | OPT_UTC_Z
    orjson_opts = OPT_NAIVE_UTC | OPT_UTC_Z

    def orjson_default(obj):
        if isinstance(obj, collections.OrderedDict):
            return dict(obj)
        raise TypeError
    def output_json_fast_orjson(request, data, code, headers=None):
        current_app = request.app
        if current_app.debug:
            return output_json_pretty(request, data, code, headers=headers)
        settings = current_app.config.get('RESTPLUS_JSON', {})
        dumped = fast_dumps(data, option=orjson_opts, default=orjson_default, **settings) + b"\n"
        resp = HTTPResponse(None, code, headers, content_type='application/json', body_bytes=dumped)
        return resp
    output_json_fast = output_json_fast_orjson
else:
    output_json_fast = output_json_pretty
