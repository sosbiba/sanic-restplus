# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from six import with_metaclass

# from flask import request
# from flask.views import MethodView
from sanic.views import HTTPMethodView
from sanic.response import HTTPResponse
from sanic.constants import HTTP_METHODS

# from werkzeug.wrappers import BaseResponse

from .model import ModelBase

from .utils import unpack, best_match_accept_mimetype


class MethodViewExt(HTTPMethodView):
    methods = None

class ResourceMeta(type):
    def __new__(mcs, name, bases, d):
        p_type = type.__new__(mcs, name, bases, d)
        if 'methods' not in d:
            methods = set(p_type.methods or [])
            for m in HTTP_METHODS:
                if m.lower() in d:
                    methods.add(m)
            # If we have no method at all in there we don't want to
            # add a method list.  (This is for instance the case for
            # the base class or another subclass of a base method view
            # that does not introduce new methods).
            if methods:
                p_type.methods = sorted(methods)
        return p_type


class Resource(with_metaclass(ResourceMeta, MethodViewExt)):
    '''
    Represents an abstract RESTPlus resource.

    Concrete resources should extend from this class
    and expose methods for each supported HTTP method.
    If a resource is invoked with an unsupported HTTP method,
    the API will return a response with status 405 Method Not Allowed.
    Otherwise the appropriate method is called and passed all arguments
    from the url rule used when adding the resource to an Api instance.
    See :meth:`~flask_restplus.Api.add_resource` for details.
    '''

    representations = None
    method_decorators = []


    def __init__(self, api=None, *args, **kwargs):
        self.api = api

    def dispatch_request(self, request, *args, **kwargs):

        meth = getattr(self, request.method.lower(), None)
        if meth is None and request.method == 'HEAD':
            meth = getattr(self, 'get', None)
        assert meth is not None, 'Unimplemented method %r' % request.method

        for decorator in self.method_decorators:
            meth = decorator(meth)

        self.validate_payload(request, meth)

        resp = meth(*args, **kwargs)

        if isinstance(resp, HTTPResponse):
            return resp

        representations = self.representations or {}

        mediatype = best_match_accept_mimetype(request, representations, default=None)
        if mediatype in representations:
             data, code, headers = unpack(resp)
             resp = representations[mediatype](data, code, headers)
             resp.headers['Content-Type'] = mediatype
             return resp

        return resp

    def __validate_payload(self, request, expect, collection=False):
        '''
        :param ModelBase expect: the expected model for the input payload
        :param bool collection: False if a single object of a resource is
        expected, True if a collection of objects of a resource is expected.
        '''
        # TODO: proper content negotiation
        data = request.get_json()
        if collection:
            data = data if isinstance(data, list) else [data]
            for obj in data:
                expect.validate(obj, self.api.refresolver, self.api.format_checker)
        else:
            expect.validate(data, self.api.refresolver, self.api.format_checker)

    def validate_payload(self, request, func):
        '''Perform a payload validation on expected model if necessary'''
        if getattr(func, '__apidoc__', False) is not False:
            doc = func.__apidoc__
            validate = doc.get('validate', None)
            validate = validate if validate is not None else self.api._validate
            if validate:
                for expect in doc.get('expect', []):
                    # TODO: handle third party handlers
                    if isinstance(expect, list) and len(expect) == 1:
                        if isinstance(expect[0], ModelBase):
                            self.__validate_payload(request, expect[0], collection=True)
                    if isinstance(expect, ModelBase):
                        self.__validate_payload(request, expect, collection=False)
