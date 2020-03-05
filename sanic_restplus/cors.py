# -*- coding: utf-8 -*-
#
from asyncio import iscoroutinefunction
from datetime import timedelta
from functools import update_wrapper

from sanic.constants import HTTP_METHODS
from sanic.request import Request as sanic_request
from sanic.response import HTTPResponse
from sanic.views import HTTPMethodView

from sanic_restplus.utils import unpack


def crossdomain(origin=None, methods=None, headers=None, expose_headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True, credentials=False):
    if methods is not None:
        m = list(sorted(x.upper() for x in methods))
        if 'OPTIONS' not in m:
            m.append('OPTIONS')
        methods = ', '.join(m)
    if headers is not None and not isinstance(headers, str):
        headers = ', '.join(x.upper() for x in headers)
    if expose_headers is not None and not isinstance(expose_headers, str):
        expose_headers = ', '.join(x.upper() for x in expose_headers)
    if not isinstance(origin, str):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods
        # Todo:
        #  This is wrong for now, we need a way to find
        #  only the methods the httpmethodview contains
        return ', '.join(HTTP_METHODS)

    def decorator(f):
        async def wrapped_function(*args, **kwargs):
            orig_args = list(args)
            args_len = len(orig_args)
            rt = RuntimeError("Must only use crossdomain decorator on a function that takes 'request' as "
                              "first or second argument")
            if args_len < 1:
                #weird, no args
                raise rt
            elif args_len < 2:
                request = orig_args.pop(0)
                args = (request,)
            else:
                next_arg = orig_args.pop(0)
                args = list()
                if isinstance(next_arg, HTTPMethodView) or issubclass(next_arg, HTTPMethodView):
                    args.append(next_arg)  # self or cls
                    next_arg = orig_args.pop(0)
                request = next_arg
                args.append(request)
                args.extend(orig_args)
                args = tuple(args)
            if not isinstance(request, sanic_request):
                raise rt
            do_await = iscoroutinefunction(f)
            if automatic_options and request.method == 'OPTIONS':
                resp = HTTPResponse()
            else:
                resp = f(*args, **kwargs)
                if do_await:
                    resp = await resp
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            def apply_cors(h):
                nonlocal origin, get_methods, max_age, credentials, headers, expose_headers
                h['Access-Control-Allow-Origin'] = origin
                h['Access-Control-Allow-Methods'] = get_methods()
                h['Access-Control-Max-Age'] = str(max_age)
                if credentials:
                    h['Access-Control-Allow-Credentials'] = 'true'
                if headers is not None:
                    h['Access-Control-Allow-Headers'] = headers
                if expose_headers is not None:
                    h['Access-Control-Expose-Headers'] = expose_headers

            if isinstance(resp, HTTPResponse):
                apply_cors(resp.headers)
            elif isinstance(resp, tuple):
                resp, status, h = unpack(resp)
                apply_cors(h)
                resp = resp, status, h
            elif isinstance(resp, (str, list, dict, set, frozenset)):
                h = dict()
                apply_cors(h)
                resp = resp, 200, h
            else:
                raise RuntimeError("crossorigin wrapper did not get a valid response from the wrapped function")
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator
