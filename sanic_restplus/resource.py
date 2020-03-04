# -*- coding: utf-8 -*-
#
import inspect
from asyncio import iscoroutinefunction
from sanic.views import HTTPMethodView
from sanic.response import BaseHTTPResponse
from sanic.constants import HTTP_METHODS

from .model import ModelBase

from .utils import unpack, best_match_accept_mimetype


class MethodViewExt(HTTPMethodView):
    methods = None
    method_has_context = None

    @classmethod
    def as_view_named(cls, endpoint_name, *class_args, **class_kwargs):
        """Return view function for use with the routing system, that
        dispatches request to appropriate handler method.
        """

        view = super(MethodViewExt, cls).as_view(*class_args, **class_kwargs)
        view.__name__ = endpoint_name
        return view

class ResourceMeta(type):
    def __new__(mcs, name, bases, d):
        p_type = type.__new__(mcs, name, bases, d)
        if 'methods' not in d:
            methods = set(p_type.methods or [])
            method_has_context = p_type.method_has_context or {}
            for m in HTTP_METHODS:
                ml = m.lower()
                func = d.get(ml, None)
                if func:
                    methods.add(m)
                    s = inspect.signature(func)
                    if len(s.parameters) < 3:
                        continue
                    # We have more than just 'self' and 'request'
                    p = iter(s.parameters.items())
                    next(p)  # self/cls
                    next(p)  # request
                    p = list(p)
                    for (i, (k, v)) in enumerate(p):
                        if v.name == "context":
                            if v.default == v.empty:
                                method_has_context[m] = i+2
                            else:
                                method_has_context[m] = 'k'
                            continue


            # If we have no method at all in there we don't want to
            # add a method list.  (This is for instance the case for
            # the base class or another subclass of a base method view
            # that does not introduce new methods).
            if methods:
                p_type.methods = sorted(methods)
            p_type.method_has_context = method_has_context
        return p_type


class Resource(MethodViewExt, metaclass=ResourceMeta):
    """
    Represents an abstract sanic_restplus.Resource.

    Concrete resources should extend from this class
    and expose methods for each supported HTTP method.
    If a resource is invoked with an unsupported HTTP method,
    the API will return a response with status 405 Method Not Allowed.
    Otherwise the appropriate method is called and passed all arguments
    from the url rule used when adding the resource to an Api instance.
    See :meth:`~sanic_restplus.Api.add_resource` for details.
    """

    representations = None
    method_decorators = []

    def __init__(self, api=None, *args, **kwargs):
        self.api = api

    async def dispatch_request(self, request, *args, **kwargs):
        context = kwargs.pop('context', None)
        has_context = bool(context)
        requestmethod = request.method
        meth = getattr(self, requestmethod.lower(), None)
        if meth is None and requestmethod == 'HEAD':
            meth = getattr(self, 'get', None)
            requestmethod = 'GET'
        elif meth is None and requestmethod == 'OPTIONS':
            meth = getattr(self, 'get', None)
            requestmethod = 'GET'
        assert meth is not None, 'Unimplemented method {0!r}'.format(requestmethod)
        method_has_context = self.method_has_context.get(requestmethod, False)
        for decorator in self.method_decorators:
            meth = decorator(meth)

        self.validate_payload(request, meth)
        if has_context and method_has_context:
            if method_has_context == 'k' or len(kwargs) > 0:
                kwargs.setdefault('context', context)
            else:
                pos = int(method_has_context) - 2  # skip self and request
                args = list(args)
                args.insert(pos, context)
        do_await = iscoroutinefunction(meth)
        resp = meth(request, *args, **kwargs)
        if do_await:
            resp = await resp
        resp_type = type(resp)
        if issubclass(resp_type, BaseHTTPResponse):
            return resp
        elif inspect.isawaitable(resp):
            # Still have a coroutine or awaitable even after waiting.
            # let the output handler handle it
            return resp

        representations = self.representations or {}

        mediatype = best_match_accept_mimetype(request, representations, default=None)
        if mediatype in representations:
             # resp might be a coroutine. Wait for it
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
        data = request.json
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
