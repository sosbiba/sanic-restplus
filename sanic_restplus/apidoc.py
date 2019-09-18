# -*- coding: utf-8 -*-
#
import os
import sys
from sanic import Blueprint
from sanic_jinja2_spf import sanic_jinja2, PackageLoader
from spf import SanicPluginsFramework

async_req_version = (3, 6)
cur_py_version = sys.version_info

class Apidoc(Blueprint):
    def __init__(self, *args, **kwargs):
        self.registered = False
        self.app = None
        super(Apidoc, self).__init__(*args, **kwargs)

    def register(self, *args, **kwargs):
        app = args[0]
        self.app = app
        super(Apidoc, self).register(*args, **kwargs)
        self.registered = True

    @property
    def config(self):
        if self.app:
            return self.app.config
        return {}

    def url_for(self, *args, **kwargs):
        return self.app.url_for(*args, **kwargs)


apidoc = Apidoc('restplus_doc', None)
spf = SanicPluginsFramework(apidoc)
loader = PackageLoader(__name__, 'templates')
if cur_py_version >= async_req_version:
    j2 = spf.register_plugin(sanic_jinja2, loader=loader, enable_async=True)
else:
    j2 = spf.register_plugin(sanic_jinja2, loader=loader)

module_path = os.path.abspath(os.path.dirname(__file__))
module_static = os.path.join(module_path, 'static')
if os.path.isdir(module_static):
    apidoc.static('/swaggerui', module_static)
else:
    apidoc.static('/swaggerui', './sanic_restplus/static')


def swagger_static(filename):
    if apidoc.url_prefix and len(apidoc.url_prefix) > 0:
        return '{}/swaggerui/{}'.format(apidoc.url_prefix, filename)
    return '/swaggerui/{}'.format(filename)
    # Sanic cannot do named routes for static file routes at the moment
    # return apidoc.url_for('restplus_doc.static', filename=filename)


def config():
    return apidoc.config


if cur_py_version >= async_req_version:
    async def ui_for(request, api, request_context):
        """Render a SwaggerUI for a given API"""
        j2.add_env('swagger_static', swagger_static)
        j2.add_env('config', config())
        return await j2.render_async('swagger-ui.html', request, title=api.title,
                                     specs_url=api.specs_url, additional_css=api.additional_css)
else:
    def ui_for(request, api, request_context):
        """Render a SwaggerUI for a given API"""
        j2.add_env('swagger_static', swagger_static)
        j2.add_env('config', config())
        return j2.render('swagger-ui.html', request, title=api.title,
                         specs_url=api.specs_url, additional_css=api.additional_css)
