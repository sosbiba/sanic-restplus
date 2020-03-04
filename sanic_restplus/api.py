# -*- coding: utf-8 -*-
#
import sys
import os
import asyncio
import difflib
import inspect
from asyncio import iscoroutinefunction
from itertools import chain
import logging
import operator
import re

from collections import OrderedDict
from functools import wraps, partial, lru_cache, update_wrapper
from types import MethodType

from jinja2 import PackageLoader
from sanic.router import RouteExists, url_hash
from sanic.response import text, BaseHTTPResponse
from sanic.views import HTTPMethodView
from sanic_jinja2_spf import sanic_jinja2 as sanic_jinja2_plugin
from sanic_jinja2 import SanicJinja2
from spf.plugin import FutureRoute, FutureStatic

try:
    from sanic.response import ALL_STATUS_CODES
except ImportError:
    from sanic.response import STATUS_CODES as ALL_STATUS_CODES
from sanic.handlers import ErrorHandler
from sanic.exceptions import SanicException, InvalidUsage, NotFound, abort
from sanic import exceptions, Sanic, Blueprint
try:
    from sanic.compat import Header
except ImportError:
    try:
        from sanic.server import CIMultiDict as Header
    except ImportError:
        from sanic.server import CIDict as Header
from spf import SanicPluginsFramework
from jsonschema import RefResolver

from .restplus import restplus
from .mask import ParseError, MaskError
from .namespace import Namespace
from .postman import PostmanCollectionV1
from .resource import Resource
from .swagger import Swagger
from .utils import default_id, camel_to_dash, unpack, best_match_accept_mimetype, get_accept_mimetypes
from .representations import output_json
from ._http import HTTPStatus

async_req_version = (3, 6)
cur_py_version = sys.version_info

RE_RULES = re.compile('(<.*>)')

# List headers that should never be handled by Flask-RESTPlus
HEADERS_BLACKLIST = ('Content-Length',)

DEFAULT_REPRESENTATIONS = [('application/json', output_json)]

log = logging.getLogger(__name__)


class Api(object):
    '''
    The endpoint parameter prefix all views and resources:

        - The API root/documentation will be ``{endpoint}.root``
        - A resource registered as 'resource' will be available as ``{endpoint}.resource``

    :param sanic.Sanic|sanic.Blueprint app: the Flask application object or a Blueprint
    :param str version: The API version (used in Swagger documentation)
    :param str title: The API title (used in Swagger documentation)
    :param str description: The API description (used in Swagger documentation)
    :param str terms_url: The API terms page URL (used in Swagger documentation)
    :param str contact: A contact email for the API (used in Swagger documentation)
    :param str license: The license associated to the API (used in Swagger documentation)
    :param str license_url: The license page URL (used in Swagger documentation)
    :param str endpoint: The API base endpoint (default to 'api).
    :param str default: The default namespace base name (default to 'default')
    :param str default_label: The default namespace label (used in Swagger documentation)
    :param str default_mediatype: The default media type to return
    :param bool validate: Whether or not the API should perform input payload validation.
    :param bool ordered: Whether or not preserve order models and marshalling.
    :param str doc: The documentation path. If set to a false value, documentation is disabled.
                (Default to '/')
    :param list decorators: Decorators to attach to every resource
    :param bool catch_all_404s: Use :meth:`handle_error`
        to handle 404 errors throughout your app
    :param dict authorizations: A Swagger Authorizations declaration as dictionary
    :param bool serve_challenge_on_401: Serve basic authentication challenge with 401
        responses (default 'False')
    :param FormatChecker format_checker: A jsonschema.FormatChecker object that is hooked into
        the Model validator. A default or a custom FormatChecker can be provided (e.g., with custom
        checkers), otherwise the default action is to not enforce any format validation.
    '''

    uid_counter = 0
    def __init__(self, spf_reg=None, version='1.0', title=None, description=None,
            terms_url=None, license=None, license_url=None,
            contact=None, contact_url=None, contact_email=None,
            authorizations=None, security=None, doc='/', default_id=default_id,
            default='default', default_label='Default namespace', validate=None,
            tags=None, prefix='', ordered=False,
            default_mediatype='application/json', decorators=None,
            catch_all_404s=False, serve_challenge_on_401=False, format_checker=None,
            additional_css=None, **kwargs):
        self.version = version
        self.title = title or 'API'
        self.description = description
        self.terms_url = terms_url
        self.contact = contact
        self.contact_email = contact_email
        self.contact_url = contact_url
        self.license = license
        self.license_url = license_url
        self.authorizations = authorizations
        self.security = security
        self.default_id = default_id
        self.ordered = ordered
        self._validate = validate
        self._doc = doc
        self._doc_view = None
        self._default_error_handler = None
        self.tags = tags or []

        self.error_handlers = {
            ParseError: mask_parse_error_handler,
            MaskError: mask_error_handler,
        }
        self._schema = None
        self.models = {}
        self._refresolver = None
        self.format_checker = format_checker
        self.namespaces = []
        self.default_namespace = self.namespace(default, default_label,
            endpoint='{0}-declaration'.format(default),
            validate=validate,
            api=self,
            path='/',
        )
        self.ns_paths = dict()

        self.representations = OrderedDict(DEFAULT_REPRESENTATIONS)
        self.urls = {}
        self.prefix = prefix
        self.default_mediatype = default_mediatype
        self.decorators = decorators if decorators else []
        self.catch_all_404s = catch_all_404s
        self.serve_challenge_on_401 = serve_challenge_on_401
        self.blueprint_setup = None
        self.endpoints = set()
        self.resources = []
        self.spf_reg = None
        self.blueprint = None
        self.additional_css = additional_css
        Api.uid_counter += 1
        self._uid = Api.uid_counter

        if spf_reg is not None:
            if isinstance(spf_reg, Sanic):
                # use legacy init method
                spf = SanicPluginsFramework(spf_reg)
                try:
                    spf_reg = restplus.find_plugin_registration(spf)
                except LookupError:
                    raise RuntimeError("Cannot create Api before sanic_restplus is registered on the SPF.")
            self.init_api(reg=spf_reg, **kwargs)

    def init_api(self, reg=None, **kwargs):
        '''
        Allow to lazy register the API on a SPF instance::

        >>> app = Sanic(__name__)
        >>> spf = SanicPluginsFramework(app)
        >>> reg = spf.register_plugin(restplus)
        >>> api = Api()
        >>> api.init_api(reg)

        :param PluginRegistration reg: The reg handle of the extension registered against the app
        :param str title: The API title (used in Swagger documentation)
        :param str description: The API description (used in Swagger documentation)
        :param str terms_url: The API terms page URL (used in Swagger documentation)
        :param str contact: A contact email for the API (used in Swagger documentation)
        :param str license: The license associated to the API (used in Swagger documentation)
        :param str license_url: The license page URL (used in Swagger documentation)

        '''
        if self.spf_reg is None:
            if reg is not None:
                self.spf_reg = reg
            else:
                raise RuntimeError("Cannot init_api without self.spf_reg")
        self.title = kwargs.get('title', self.title)
        self.description = kwargs.get('description', self.description)
        self.terms_url = kwargs.get('terms_url', self.terms_url)
        self.contact = kwargs.get('contact', self.contact)
        self.contact_url = kwargs.get('contact_url', self.contact_url)
        self.contact_email = kwargs.get('contact_email', self.contact_email)
        self.license = kwargs.get('license', self.license)
        self.license_url = kwargs.get('license_url', self.license_url)
        self.additional_css = kwargs.get('additional_css', self.additional_css)
        self._add_specs = kwargs.get('add_specs', True)

        context = restplus.get_context_from_spf(self.spf_reg)
        app = context.app
        # If app is a blueprint, defer the initialization
        if isinstance(app, Blueprint):
            orig_reg = app.register
            def new_reg(_app, _options):
                nonlocal self, orig_reg
                r = orig_reg(_app, _options)
                self._deferred_blueprint_init(r)
                return r
            self.blueprint = app
            self.blueprint.register = update_wrapper(new_reg, orig_reg)
        else:
            self._init_app(app, context)



    def _init_app(self, app, context):
        """
        Perform initialization actions with the given :class:`sanic.Sanic` object.

        :param sanic.Sanic app: The sanic application object
        """
        render_api_fn = self._setup_jinja2_renderer()
        self._register_specs()
        self._register_doc(render_api_fn)
        self._register_static()

        app.error_handler = ApiErrorHandler(app.error_handler, self)
        #app.handle_user_exception = partial(self.error_router, app.handle_user_exception)

        if len(self.resources) > 0:
            for resource, namespace, urls, kwargs in self.resources:
                self._register_view(resource, namespace, *urls, **kwargs)

        #self._register_apidoc(app)
        self._validate = self._validate if self._validate is not None else app.config.get('RESTPLUS_VALIDATE', False)
        app.config.setdefault('RESTPLUS_MASK_HEADER', 'X-Fields')
        app.config.setdefault('RESTPLUS_MASK_SWAGGER', True)
        context.MASK_HEADER = app.config['RESTPLUS_MASK_HEADER']
        context.MASK_SWAGGER = app.config['RESTPLUS_MASK_SWAGGER']


    def __getattr__(self, name):
        try:
            return getattr(self.default_namespace, name)
        except AttributeError:
            raise AttributeError('Api does not have {0} attribute'.format(name))

    def _complete_url(self, url_part, registration_prefix):
        '''
        This method is used to defer the construction of the final url in
        the case that the Api is created with a Blueprint.

        :param url_part: The part of the url the endpoint is registered with
        :param registration_prefix: The part of the url contributed by the
            blueprint.  Generally speaking, BlueprintSetupState.url_prefix
        '''
        parts = (registration_prefix, self.prefix, url_part)
        return ''.join(part for part in parts if part)

    # def _register_apidoc(self, app):
    #     context = restplus.get_context_from_spf(self.spf_reg)
    #     if not context.get('apidoc_registered', False):
    #         app.blueprint(apidoc.apidoc, url_prefix=self.prefix)
    #         context['apidoc_registered'] = True
    #     else:
    #         warnings.warn("Attempting to re-register the apidoc blueprint, skipped.")

    def _setup_jinja2_renderer(self):
        spf, plugin_name, plugin_prefix = self.spf_reg
        loader = PackageLoader(__name__, 'templates')
        enable_async = cur_py_version >= async_req_version
        context = restplus.get_context_from_spf(self.spf_reg)
        # Don't try to use an already registered Jinja2-plugin, it causes too much incompatibility with template
        # loaders. Just use a new one of our own.
        j2 = SanicJinja2(context.app, loader=loader, pkg_name=plugin_name, enable_async=enable_async)

        def swagger_static(filename):
            nonlocal self
            spf, plugin_name, plugin_prefix = self.spf_reg
            endpoint = '{}.static'.format(str(self._uid))
            return restplus.spf_resolve_url_for(spf, endpoint, filename=filename)

        def config():
            nonlocal self, context
            app = context.app
            if isinstance(app, Blueprint):
                return {}
            return app.config

        if enable_async:
            async def api_renderer(request, api, request_context):
                """Render a SwaggerUI for a given API"""
                nonlocal j2, swagger_static, config
                j2.add_env('swagger_static', swagger_static)
                j2.add_env('config', config())
                return await j2.render_async('swagger-ui.html', request, title=api.title,
                                             specs_url=api.specs_url, additional_css=api.additional_css)
        else:
            def api_renderer(request, api, request_context):
                """Render a SwaggerUI for a given API"""
                nonlocal j2, swagger_static, config
                j2.add_env('swagger_static', swagger_static)
                j2.add_env('config', config())
                return j2.render('swagger-ui.html', request, title=api.title,
                                 specs_url=api.specs_url, additional_css=api.additional_css)
        return api_renderer

    def _register_static(self):
        (spf, plugin_name, plugin_url_prefix) = self.spf_reg
        context = restplus.get_context_from_spf(self.spf_reg)
        module_path = os.path.abspath(os.path.dirname(__file__))
        module_static = os.path.join(module_path, 'static')
        endpoint = '{}.static'.format(str(self._uid))
        kwargs = { "name": endpoint }
        if os.path.isdir(module_static):
            s = FutureStatic('/swaggerui', module_static, (), kwargs)
        else:
            s = FutureStatic('/swaggerui', './sanic_restplus/static', (), kwargs)
        spf._register_static_helper(s, spf, restplus, context, plugin_name, plugin_url_prefix)


    def _register_specs(self):
        if self._add_specs:
            endpoint = '{}_specs'.format(str(self._uid))
            self._register_view(
                SwaggerView,
                self.default_namespace,
                '/swagger.json',
                endpoint=endpoint,
                resource_class_args=(self, )
            )
            self.endpoints.add(endpoint)

    def _register_doc(self, api_renderer):
        root_path = self.prefix or '/'
        (spf, plugin_name, plugin_url_prefix) = self.spf_reg
        context = restplus.get_context_from_spf(self.spf_reg)
        if self._add_specs and self._doc:
            doc_endpoint_name = '{}_doc'.format(str(self._uid))

            def _render_doc(*args, **kwargs):
                nonlocal self, api_renderer
                return self.render_doc(*args, api_renderer=api_renderer, **kwargs)
            render_doc = wraps(self.render_doc)(_render_doc)
            render_doc.__name__ = doc_endpoint_name
            r = FutureRoute(render_doc, self._doc, (), {'with_context': True})
            spf._register_route_helper(r, spf, restplus, context, plugin_name, plugin_url_prefix)
        if self._doc != root_path:
            try:# app_or_blueprint.add_url_rule(self.prefix or '/', 'root', self.render_root)
                root_endpoint_name = '{}_root'.format(str(self._uid))
                def _render_root(*args, **kwargs):
                    nonlocal self
                    return self.render_root(*args, **kwargs)
                render_root = wraps(self.render_root)(_render_root)
                render_root.__name__ = root_endpoint_name
                r = FutureRoute(render_root, root_path, (), {})
                spf._register_route_helper(r, spf, restplus, context, plugin_name, plugin_url_prefix)

            except RouteExists:
                pass

    def register_resource(self, namespace, resource, *urls, **kwargs):
        endpoint = kwargs.pop('endpoint', None)
        endpoint = str(endpoint or self.default_endpoint(resource, namespace))

        kwargs['endpoint'] = endpoint
        self.endpoints.add(endpoint)

        if self.spf_reg is not None:
            self._register_view(resource, namespace, *urls, **kwargs)
        else:
            self.resources.append((resource, namespace, urls, kwargs))
        return endpoint

    def _register_view(self, resource, namespace, *urls, **kwargs):
        endpoint = kwargs.pop('endpoint', None) or camel_to_dash(resource.__name__)
        resource_class_args = kwargs.pop('resource_class_args', ())
        resource_class_kwargs = kwargs.pop('resource_class_kwargs', {})
        (spf, plugin_name, plugin_url_prefix) = self.spf_reg
        resource.mediatypes = self.mediatypes_method()  # Hacky
        resource.endpoint = endpoint
        methods = resource.methods
        if methods is None or len(methods) < 1:
            methods = ['GET', 'OPTIONS']
        else:
            methods = list(methods)
        if 'OPTIONS' not in methods:
            methods.append('OPTIONS')  # Always add options, so CORS will work properly
        resource_func = self.output(resource.as_view_named(endpoint, self, *resource_class_args,
                                                           **resource_class_kwargs))
        for decorator in chain(namespace.decorators, self.decorators):
            resource_func = decorator(resource_func)

        context = restplus.get_context_from_spf(self.spf_reg)
        for url in urls:
            # If this Api has a blueprint
            if self.blueprint:
                # And this Api has been setup
                if self.blueprint_setup:
                    # Set the rule to a string directly, as the blueprint is already
                    # set up.
                    self.blueprint_setup.add_url_rule(url, view_func=resource_func, methods=methods, **kwargs)
                    continue
                else:
                    # Set the rule to a function that expects the blueprint prefix
                    # to construct the final url.  Allows deferment of url finalization
                    # in the case that the associated Blueprint has not yet been
                    # registered to an application, so we can wait for the registration
                    # prefix
                    rule = partial(self._complete_url, url)
            else:
                # If we've got no Blueprint, just build a url with no prefix
                rule = self._complete_url(url, '')
            # Add the url to the application or blueprint
            r = FutureRoute(resource_func, rule, (), {'methods': methods, 'with_context': True})
            spf._register_route_helper(r, spf, restplus, context, plugin_name, plugin_url_prefix)

    def output(self, resource):
        """
        Wraps a resource (as a Sanic view function),
        for cases where the resource does not directly return a response object

        :param resource: The resource as a Sanic view function
        """
        @wraps(resource)
        async def wrapper(request, *args, **kwargs):
            view_class = getattr(resource, 'view_class', None)
            is_method_view = bool(view_class) and issubclass(view_class, HTTPMethodView)
            do_await = iscoroutinefunction(resource)
            resp = resource(request, *args, **kwargs)
            if do_await:
                resp = await resp
            elif is_method_view:
                # MethodView could wrap coroutines, without being a coroutine itself.
                if inspect.isawaitable(resp):
                    resp = await resp
            resp_type = type(resp)
            if issubclass(resp_type, BaseHTTPResponse):
                return resp
            elif inspect.isawaitable(resp):
                # Can't unpack an awaitable.
                raise RuntimeError("RestPlus output handler received a non-awaited coroutine or Task.")
            data, code, headers = unpack(resp)
            return self.make_response(request, data, code, headers=headers)
        return wrapper

    def make_response(self, request, data, *args, **kwargs):
        """
        Looks up the representation transformer for the requested media
        type, invoking the transformer to create a response object. This
        defaults to default_mediatype if no transformer is found for the
        requested mediatype. If default_mediatype is None, a 406 Not
        Acceptable response will be sent as per RFC 2616 section 14.1

        :param data: Python object containing response data to be transformed
        """
        default_mediatype = kwargs.pop('fallback_mediatype', None) or self.default_mediatype
        mediatype = best_match_accept_mimetype(request,
            self.representations,
            default=default_mediatype,
        )
        if mediatype is None:
            raise exceptions.SanicException("Not Acceptable", 406)
        if mediatype in self.representations:
            resp = self.representations[mediatype](request, data, *args, **kwargs)
            resp.headers['Content-Type'] = mediatype
            return resp
        elif mediatype == 'text/plain':
            resp = text(str(data), *args, **kwargs)
            resp.headers['Content-Type'] = 'text/plain'
            return resp
        else:
            raise exceptions.ServerError(None)

    def documentation(self, func):
        '''A decorator to specify a view function for the documentation'''
        self._doc_view = func
        return func

    def render_root(self, request):
        self.abort(HTTPStatus.NOT_FOUND)

    async def render_doc(self, request, context, api_renderer=None):
        '''Override this method to customize the documentation page'''
        if self._doc_view:
            response = self._doc_view()
        elif not self._doc:
            return abort(HTTPStatus.NOT_FOUND)
        elif api_renderer is None:
            raise RuntimeError("No renderer function given for Doc view")
        else:
            response = api_renderer(request, self, context)
        if asyncio.iscoroutine(response):
            response = await response
        return response

    def default_endpoint(self, resource, namespace):
        """
        Provide a default endpoint for a resource on a given namespace.

        Endpoints are ensured not to collide.

        Override this method to specify a custom algorithm for default endpoint.

        :param Resource resource: the resource for which we want an endpoint
        :param Namespace namespace: the namespace holding the resource
        :returns str: An endpoint name
        """
        endpoint = "{}_{}".format(str(self._uid), camel_to_dash(resource.__name__))
        if namespace is not self.default_namespace:
            endpoint = '{ns.name}_{endpoint}'.format(ns=namespace, endpoint=endpoint)
        if endpoint in self.endpoints:
            suffix = 2
            while True:
                new_endpoint = '{base}_{suffix}'.format(base=endpoint, suffix=suffix)
                if new_endpoint not in self.endpoints:
                    endpoint = new_endpoint
                    break
                suffix += 1
        return endpoint

    def get_ns_path(self, ns):
        return self.ns_paths.get(ns)

    def ns_urls(self, ns, urls):
        path = self.get_ns_path(ns) or ns.path
        return [path + url for url in urls]

    def add_namespace(self, ns, path=None):
        '''
        This method registers resources from namespace for current instance of api.
        You can use argument path for definition custom prefix url for namespace.

        :param Namespace ns: the namespace
        :param path: registration prefix of namespace
        '''
        if ns not in self.namespaces:
            self.namespaces.append(ns)
            if self not in ns.apis:
                ns.apis.append(self)
            # Associate ns with prefix-path
            if path is not None:
                self.ns_paths[ns] = path
        # Register resources
        for r in ns.resources:
            urls = self.ns_urls(ns, r.urls)
            self.register_resource(ns, r.resource, *urls, **r.kwargs)
        # Register models
        for name, definition in ns.models.items():
            self.models[name] = definition

    def namespace(self, *args, **kwargs):
        '''
        A namespace factory.

        :returns Namespace: a new namespace instance
        '''
        kwargs['ordered'] = kwargs.get('ordered', self.ordered)
        ns = Namespace(*args, **kwargs)
        self.add_namespace(ns)
        return ns

    def endpoint(self, name):
        if self.blueprint:
            return '{0}.{1}'.format(self.blueprint.name, name)
        else:
            return name

    @property
    def specs_url(self):
        '''
        The Swagger specifications absolute url (ie. `swagger.json`)

        :rtype: str
        '''
        try:
            specs_url = restplus.spf_resolve_url_for(self.spf_reg, self.endpoint('{}_specs'.format(str(self._uid))), _external=False)
        except (AttributeError, KeyError):
            raise RuntimeError("The API object does not have an `app` assigned.")
        return specs_url
    @property
    def base_url(self):
        '''
        The API base absolute url

        :rtype: str
        '''
        root_path = self.prefix or '/'
        try:
            if self._doc == root_path:
                base_url = restplus.spf_resolve_url_for(self.spf_reg, self.endpoint('{}_doc'.format(str(self._uid))), _external=False)
            else:
                base_url = restplus.spf_resolve_url_for(self.spf_reg, self.endpoint('{}_root'.format(str(self._uid))), _external=False)
        except (AttributeError, KeyError):
            raise RuntimeError("The API object does not have an `app` assigned.")
        return base_url


    @property
    def base_path(self):
        '''
        The API path

        :rtype: str
        '''
        root_path = self.prefix or '/'
        (spf, _, _) = self.spf_reg
        try:
            if self._doc == root_path:
                base_url = restplus.spf_resolve_url_for(self.spf_reg, self.endpoint('{}_doc'.format(str(self._uid))))
            else:
                base_url = restplus.spf_resolve_url_for(self.spf_reg, self.endpoint('{}_root'.format(str(self._uid))))
        except (AttributeError, KeyError):
            raise RuntimeError("The API object does not have an `app` assigned.")
        return base_url

    @property
    @lru_cache()
    def __schema__(self):
        '''
        The Swagger specifications/schema for this API

        :returns dict: the schema as a serializable dict
        '''
        if not self._schema:
            try:
                self._schema = Swagger(self).as_dict()
            except Exception:
                # Log the source exception for debugging purpose
                # and return an error message
                msg = 'Unable to render schema'
                log.exception(msg)  # This will provide a full traceback
                return {'error': msg}
        return self._schema

    @property
    def _own_and_child_error_handlers(self):
        rv = {}
        rv.update(self.error_handlers)
        for ns in self.namespaces:
            for exception, handler in ns.error_handlers.items():
                rv[exception] = handler
        return rv

    def errorhandler(self, exception):
        '''A decorator to register an error handler for a given exception'''
        if inspect.isclass(exception) and issubclass(exception, Exception):
            # Register an error handler for a given exception
            def wrapper(func):
                self.error_handlers[exception] = func
                return func
            return wrapper
        else:
            # Register the default error handler
            self._default_error_handler = exception
            return exception

    def owns_endpoint(self, endpoint):
        '''
        Tests if an endpoint name (not path) belongs to this Api.
        Takes into account the Blueprint name part of the endpoint name.

        :param str endpoint: The name of the endpoint being checked
        :return: bool
        '''

        if self.blueprint:
            if endpoint.startswith(self.blueprint.name):
                endpoint = endpoint.split(self.blueprint.name + '.', 1)[-1]
            else:
                return False
        return endpoint in self.endpoints

    @staticmethod
    def _dummy_router_get(router, method, request):
        url = request.path
        route = router.routes_static.get(url)
        method_not_supported = InvalidUsage(
            'Method {} not allowed for URL {}'.format(
                method, url), status_code=405)
        if route:
            if route.methods and method not in route.methods:
                method_not_supported.valid_methods = route.methods
                raise method_not_supported
            match = route.pattern.match(url)
        else:
            route_found = False
            # Move on to testing all regex routes
            for route in router.routes_dynamic[url_hash(url)]:
                match = route.pattern.match(url)
                route_found |= match is not None
                # Do early method checking
                if match and method in route.methods:
                    break
            else:
                # Lastly, check against all regex routes that cannot be hashed
                for route in router.routes_always_check:
                    match = route.pattern.match(url)
                    route_found |= match is not None
                    # Do early method checking
                    if match and method in route.methods:
                        break
                else:
                    # Route was found but the methods didn't match
                    if route_found:
                        method_not_supported.valid_methods = route.methods
                        raise method_not_supported
                    raise NotFound('Requested URL {} not found'.format(url))

        return route

    def _should_use_fr_error_handler(self, request):
        '''
        Determine if error should be handled with Sanic-Restplus or default Sanic

        The goal is to return Sanic error handlers for non-SR-related routes,
        and SR errors (with the correct media type) for SR endpoints. This
        method currently handles 404 and 405 errors.

        :return: bool
        '''
        if request is None:
            # This must be a Sanic error if request is None.
            return False
        try:
            app = request.app
        except AttributeError:
            # if request doesn't have .app, then it is also a Sanic error
            return False
        try:
            return self._dummy_router_get(app.router, request.method, request)
        except InvalidUsage as e:
            (_, plugin_name, _) = self.spf_reg
            plugin_name_prefix = "{}.".format(plugin_name)
            # Check if the other HTTP methods at this url would hit the Api
            try:
                try_route_method = next(iter(e.valid_methods))
            except (AttributeError, KeyError):
                if request.method == "GET":
                    try_route_method = "POST"
                else:
                    try_route_method = "GET"
            route = self._dummy_router_get(app.router, try_route_method, request)
            route_endpoint_name = route.name
            if str(route_endpoint_name).startswith(plugin_name_prefix):
                route_endpoint_name = route_endpoint_name[len(plugin_name_prefix):]
            return self.owns_endpoint(route_endpoint_name)
        except NotFound:
            return self.catch_all_404s
        except Exception:
            # Other stuff throws other kinds of exceptions, such as Redirect
            pass

    def _has_fr_route(self, request):
        '''Encapsulating the rules for whether the request was to a Flask endpoint'''
        # 404's, 405's, which might not have a url_rule
        route = self._should_use_fr_error_handler(request)
        if route is True:
            return True
        # for all other errors, just check if FR dispatched the route
        if not route or not route.handler or not route.name:
            return False
        route_endpoint_name = route.name
        (_, plugin_name, _) = self.spf_reg
        plugin_name_prefix = "{}.".format(plugin_name)
        if str(route_endpoint_name).startswith(plugin_name_prefix):
            route_endpoint_name = route_endpoint_name[len(plugin_name_prefix):]
        return self.owns_endpoint(route_endpoint_name)

    def handle_error(self, request, e):
        """
        Error handler for the API transforms a raised exception into a Sanic response,
        with the appropriate HTTP status code and body.
        :param request: The Sanic Request object
        :type request: sanic.request.Request
        :param e: the raised Exception object
        :type e: Exception
        """
        context = restplus.get_context_from_spf(self.spf_reg)
        app = context.app
        #got_request_exception.send(app._get_current_object(), exception=e)
        if not isinstance(e, SanicException) and app.config.get('PROPAGATE_EXCEPTIONS', False):
            exc_type, exc_value, tb = sys.exc_info()
            if exc_value is e:
                raise
            else:
                raise e

        include_message_in_response = app.config.get("ERROR_INCLUDE_MESSAGE", True)
        include_code_in_response = app.config.get("ERROR_INCLUDE_CODE", True)
        default_data = {}
        headers = Header()
        for typecheck, handler in self._own_and_child_error_handlers.items():
            if isinstance(e, typecheck):
                result = handler(e)
                default_data, code, headers = unpack(result, HTTPStatus.INTERNAL_SERVER_ERROR)
                break
        else:
            if isinstance(e, SanicException):
                sanic_code = code = e.status_code
                if sanic_code is 200:
                    status = b'OK'
                # x is y comparison only works between -5 and 256
                elif sanic_code == 404:
                    status = b'Not Found'
                elif sanic_code == 500:
                    status = b'Internal Server Error'
                else:
                    status = ALL_STATUS_CODES.get(int(sanic_code))
                code = HTTPStatus(sanic_code, None)
                if status and isinstance(status, bytes):
                    status = status.decode('ascii')
                if include_message_in_response:
                    default_data = {
                        'message': getattr(e, 'message', status)
                    }

            elif self._default_error_handler:
                result = self._default_error_handler(e)
                default_data, code, headers = unpack(result, HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                code = HTTPStatus.INTERNAL_SERVER_ERROR
                status = ALL_STATUS_CODES.get(code.value, str(e))
                if status and isinstance(status, bytes):
                    status = status.decode('ascii')
                if include_message_in_response:
                    default_data = {
                        'message': status,
                    }

        if include_message_in_response:
            default_data['message'] = default_data.get('message', str(e))
        if include_code_in_response:
            default_data['code'] = int(code)

        data = getattr(e, 'data', default_data)
        fallback_mediatype = None

        if code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            exc_info = sys.exc_info()
            if exc_info[1] is None:
                exc_info = None
            context.log(logging.ERROR, exc_info)

        elif code == HTTPStatus.NOT_FOUND and app.config.get("ERROR_404_HELP", False) \
                and include_message_in_response:
            data['message'] = self._help_on_404(request, data.get('message', None))

        elif code == HTTPStatus.NOT_ACCEPTABLE and self.default_mediatype is None:
            # if we are handling NotAcceptable (406), make sure that
            # make_response uses a representation we support as the
            # default mediatype (so that make_response doesn't throw
            # another NotAcceptable error).
            supported_mediatypes = list(self.representations.keys())
            fallback_mediatype = supported_mediatypes[0] if supported_mediatypes else "text/plain"

        # Remove blacklisted headers
        for header in HEADERS_BLACKLIST:
            headers.pop(header, None)
        resp = self.make_response(request, data, code, headers, fallback_mediatype=fallback_mediatype)

        if code == HTTPStatus.UNAUTHORIZED:
            resp = self.unauthorized(resp)
        return resp

    def _help_on_404(self, request, message=None):
        raise NotImplementedError("Help on 404 is not yet implemented for Sanic-RestPlus")
        # TODO, need a way to get current app router, and plugin context, from the request
        rules = dict([(RE_RULES.sub('', rule.rule), rule.rule)
                      for rule in current_app.url_map.iter_rules()])
        close_matches = difflib.get_close_matches(request.path, rules.keys())
        if close_matches:
            # If we already have a message, add punctuation and continue it.
            message = ''.join((
                (message.rstrip('.') + '. ') if message else '',
                'You have requested this URI [',
                request.path,
                '] but did you mean ',
                ' or '.join((rules[match] for match in close_matches)),
                ' ?',
            ))
        return message

    def as_postman(self, urlvars=False, swagger=False):
        '''
        Serialize the API as Postman collection (v1)

        :param bool urlvars: whether to include or not placeholders for query strings
        :param bool swagger: whether to include or not the swagger.json specifications

        '''
        return PostmanCollectionV1(self, swagger=swagger).as_dict(urlvars=urlvars)

    def payload(self, request):
        """Default behaviour for payload() is just to return the request.json"""
        return request.json

    @property
    def refresolver(self):
        if not self._refresolver:
            self._refresolver = RefResolver.from_schema(self.__schema__)
        return self._refresolver

    @staticmethod
    def _blueprint_setup_add_url_rule_patch(blueprint_setup, rule, endpoint=None, view_func=None, **options):
        '''
        Method used to patch BlueprintSetupState.add_url_rule for setup
        state instance corresponding to this Api instance.  Exists primarily
        to enable _complete_url's function.

        :param blueprint_setup: The BlueprintSetupState instance (self)
        :param rule: A string or callable that takes a string and returns a
            string(_complete_url) that is the url rule for the endpoint
            being registered
        :param endpoint: See BlueprintSetupState.add_url_rule
        :param view_func: See BlueprintSetupState.add_url_rule
        :param **options: See BlueprintSetupState.add_url_rule
        '''

        if callable(rule):
            rule = rule(blueprint_setup.url_prefix)
        elif blueprint_setup.url_prefix:
            rule = blueprint_setup.url_prefix + rule
        options.setdefault('subdomain', blueprint_setup.subdomain)
        if endpoint is None:
            # TODO: Sanic, what do we do here?
            endpoint = _endpoint_from_view_func(view_func)
        defaults = blueprint_setup.url_defaults
        if 'defaults' in options:
            defaults = dict(defaults, **options.pop('defaults'))
        blueprint_setup.app.add_url_rule(rule, '{:s}.{:s}'.format(blueprint_setup.blueprint.name, endpoint),
                                         view_func, defaults=defaults, **options)

    def _deferred_blueprint_init(self, setup_state):
        '''
        Synchronize prefix between blueprint/api and registration options, then
        perform initialization with setup_state.app :class:`sanic.Sanic` object.
        When a :class:`sanic_restplus.Api` object is initialized with a blueprint,
        this method is recorded on the blueprint to be run when the blueprint is later
        registered to a :class:`sanic.Sanic` object.  This method also monkeypatches
        BlueprintSetupState.add_url_rule with _blueprint_setup_add_url_rule_patch.

        :param setup_state: The setup state object passed to deferred functions
            during blueprint registration
        :type setup_state: flask.blueprints.BlueprintSetupState

        '''
        raise RuntimeError("Sorry, cannot use Blueprints in Sanic-Restplus yet. We're working on it.")
        self.blueprint_setup = setup_state
        if setup_state.add_url_rule.__name__ != '_blueprint_setup_add_url_rule_patch':
            setup_state._original_add_url_rule = setup_state.add_url_rule
            setup_state.add_url_rule = MethodType(Api._blueprint_setup_add_url_rule_patch,
                                                  setup_state)
        if not setup_state.first_registration:
            raise ValueError('sanic-restplus blueprints can only be registered once.')
        self._init_app(setup_state.app)

    def mediatypes_method(self):
        '''Return a method that returns a list of mediatypes'''
        return lambda resource_cls, request:\
            self.mediatypes(request) + [self.default_mediatype]

    def mediatypes(self, request):
        '''Returns a list of requested mediatypes sent in the Accept header'''
        return [h for h, q in sorted(get_accept_mimetypes(request),
                                     key=operator.itemgetter(1), reverse=True)]

    def representation(self, mediatype):
        '''
        Allows additional representation transformers to be declared for the
        api. Transformers are functions that must be decorated with this
        method, passing the mediatype the transformer represents. Three
        arguments are passed to the transformer:

        * The data to be represented in the response body
        * The http status code
        * A dictionary of headers

        The transformer should convert the data appropriately for the mediatype
        and return a Flask response object.

        Ex::

            @api.representation('application/xml')
            def xml(data, code, headers):
                resp = make_response(convert_data_to_xml(data), code)
                resp.headers.extend(headers)
                return resp
        '''
        def wrapper(func):
            self.representations[mediatype] = func
            return func
        return wrapper

    def unauthorized(self, response):
        '''Given a response, change it to ask for credentials'''
        # TODO: Sanic implement serve_challenge_on_401 for Sanic
        #if self.serve_challenge_on_401:
        #    realm = current_app.config.get("HTTP_BASIC_AUTH_REALM", "sanic-restplus")
        #    challenge = u"{0} realm=\"{1}\"".format("Basic", realm)
        #
        #    response.headers['WWW-Authenticate'] = challenge
        return response

    def url_for(self, resource, **values):
        '''
        Generates a URL to the given resource.

        Works like :func:`app.url_for`.
        '''
        endpoint = resource.endpoint
        (spf, _, _) = self.spf_reg
        if self.blueprint:
            endpoint = '{0}.{1}'.format(self.blueprint.name, endpoint)
        return restplus.spf_resolve_url_for(self.spf_reg, endpoint, **values)


class ApiErrorHandler(ErrorHandler):
    def __init__(self, original_handler, api):
        super(ApiErrorHandler, self).__init__()
        self.original_handler = original_handler
        self.api = api

    def response(self, request, e1):
        '''
        This function decides whether the error occurred in a sanic-restplus
        endpoint or not. If it happened in a sanic-restplus endpoint, our
        handler will be dispatched. If it happened in an unrelated view, the
        app's original error handler will be dispatched.
        In the event that the error occurred in a sanic-restplus endpoint but
        the local handler can't resolve the situation, the router will fall
        back onto the original_handler as last resort.

        :param Exception e: the exception raised while handling the request
        '''
        if self.api._has_fr_route(request):
            try:
                return self.api.handle_error(request, e1)
            except Exception as e2:
                print(repr(e2))
                import traceback
                traceback.print_tb(e2.__traceback__)
                # Fall through to original handler
        return self.original_handler.response(request, e1)


class SwaggerView(Resource):
    '''Render the Swagger specifications as JSON'''
    def get(self, request):
        schema = self.api.__schema__
        return schema, HTTPStatus.INTERNAL_SERVER_ERROR if 'error' in schema else HTTPStatus.OK

    def mediatypes(self):
        return ['application/json']


def mask_parse_error_handler(error):
    '''When a mask can't be parsed'''
    return {'message': 'Mask parse error: {0}'.format(error)}, HTTPStatus.BAD_REQUEST


def mask_error_handler(error):
    '''When any error occurs on mask'''
    return {'message': 'Mask error: {0}'.format(error)}, HTTPStatus.BAD_REQUEST
