# -*- coding: utf-8 -*-
import json
import pytest

from sanic import Sanic, Blueprint
from sanic.testing import SanicTestClient
from sanic.websocket import WebSocketProtocol
from spf import SanicPluginsFramework
import sanic_restplus
from sanic_restplus import restplus

# class TestClient(SanicTestClient):
#     def get_json(self, url, status=200, **kwargs):
#         response = self.get(url, **kwargs)
#         assert response.status_code == status
#         assert response.content_type == 'application/json'
#         return json.loads(response.data.decode('utf8'))
#
#     def post_json(self, url, data, status=200, **kwargs):
#         response = self.post(url, data=json.dumps(data),
#                              headers={'content-type': 'application/json'})
#         assert response.status_code == status
#         assert response.content_type == 'application/json'
#         return json.loads(response.data.decode('utf8'))
#
#     def get_specs(self, prefix='', status=200, **kwargs):
#         '''Get a Swagger specification for a RestPlus API'''
#         return self.get_json('{0}/swagger.json'.format(prefix), status=status, **kwargs)


@pytest.fixture
def app():
    app = Sanic(__name__)
    #app.test_client_class = TestClient
    spf = SanicPluginsFramework(app)
    spf.register_plugin(restplus)
    yield app


@pytest.yield_fixture
def api(request, app):
    marker = request.node.get_closest_marker('api')
    bpkwargs = {}
    kwargs = {}
    if marker:
        if 'prefix' in marker.kwargs:
            bpkwargs['url_prefix'] = marker.kwargs.pop('prefix')
        if 'subdomain' in marker.kwargs:
            bpkwargs['subdomain'] = marker.kwargs.pop('subdomain')
        kwargs = marker.kwargs
    blueprint = Blueprint('api', __name__, **bpkwargs)
    api = sanic_restplus.Api(blueprint, **kwargs)
    app.register_blueprint(blueprint)
    yield api

@pytest.fixture
def client(loop, app, sanic_client):
    return loop.run_until_complete(sanic_client(app, protocol=WebSocketProtocol))

@pytest.fixture(autouse=True)
def _push_custom_request_context(request):
    app = request.getfixturevalue('app')
    options = request.node.get_closest_marker('request_context')

    if options is None:
        return

    ctx = app.test_request_context(*options.args, **options.kwargs)
    ctx.push()

    def teardown():
        ctx.pop()

    request.addfinalizer(teardown)
