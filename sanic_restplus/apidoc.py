# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
#from flask import url_for, Blueprint, render_template
from sanic import Blueprint
from sanic_jinja2 import SanicJinja2
from jinja2 import PackageLoader

import sys

async_req_version = (3, 6)
cur_sanic_version = sys.version_info

class Apidoc(Blueprint):
    '''
    Allow to know if the blueprint has already been registered
    until https://github.com/mitsuhiko/flask/pull/1301 is merged
    '''
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

loader = PackageLoader(__name__, 'templates')
if cur_sanic_version >= async_req_version:
    j2 = SanicJinja2(apidoc, loader, enable_async=True)
else:
    j2 = SanicJinja2(apidoc, loader)

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



# @apidoc.add_app_template_global
# def swagger_static(filename):
#     return url_for('restplus_doc.static',
#                    filename='bower/swagger-ui/dist/{0}'.format(filename))

if cur_sanic_version >= async_req_version:
    async def ui_for(request, api):
        '''Render a SwaggerUI for a given API'''
        j2.add_env('swagger_static', swagger_static)
        j2.add_env('config', config())
        return await j2.render_async('swagger-ui.html', request, title=api.title,
                               specs_url=api.specs_url, additional_css=api.additional_css)
else:
    def ui_for(request, api):
        '''Render a SwaggerUI for a given API'''
        j2.add_env('swagger_static', swagger_static)
        j2.add_env('config', config())
        return j2.render('swagger-ui.html', request, title=api.title,
                               specs_url=api.specs_url, additional_css=api.additional_css)
