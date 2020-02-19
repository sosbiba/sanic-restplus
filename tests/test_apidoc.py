# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import pytest
from sanic import Blueprint
import sanic_restplus
from sanic_restplus import restplus


class APIDocTest(object):
    async def test_default_apidoc_on_root(self, app, client):
        sanic_restplus.Api(app, version='1.0')

        assert url_for('doc') == url_for('root')

        response = await client.get(url_for('doc'))
        assert response.status_code == 200
        assert response.content_type == 'text/html; charset=utf-8'

    async def test_default_apidoc_on_root_lazy(self, app, client):
        api = sanic_restplus.Api(version='1.0')
        api.init_app(app)

        assert url_for('doc') == url_for('root')

        response = await client.get(url_for('doc'))
        assert response.status_code == 200
        assert response.content_type == 'text/html; charset=utf-8'

    async def test_default_apidoc_on_root_with_blueprint(self, app, client):
        blueprint = Blueprint('api', url_prefix='/api')
        sanic_restplus.Api(blueprint, version='1.0')
        app.register_blueprint(blueprint)

        assert url_for('api.doc') == url_for('api.root')

        response = await client.get(url_for('api.doc'))
        assert response.status_code == 200
        assert response.content_type == 'text/html; charset=utf-8'

    async def test_apidoc_with_custom_validator(self, app, client):
        app.config['SWAGGER_VALIDATOR_URL'] = 'http://somewhere.com/validator'
        sanic_restplus.Api(app, version='1.0')

        response = await client.get(url_for('doc'))
        assert response.status_code == 200
        assert response.content_type == 'text/html; charset=utf-8'
        assert 'validatorUrl: "http://somewhere.com/validator" || null,' in str(response.data)

    async def test_apidoc_doc_expansion_parameter(self, app, client):
        sanic_restplus.Api(app)

        response = await client.get(url_for('doc'))
        assert 'docExpansion: "none"' in str(response.data)

        app.config['SWAGGER_UI_DOC_EXPANSION'] = 'list'
        response = await client.get(url_for('doc'))
        assert 'docExpansion: "list"' in str(response.data)

        app.config['SWAGGER_UI_DOC_EXPANSION'] = 'full'
        response = await client.get(url_for('doc'))
        assert 'docExpansion: "full"' in str(response.data)

    async def test_apidoc_doc_display_operation_id(self, app, client):
        sanic_restplus.Api(app)

        response = await client.get(url_for('doc'))
        assert 'displayOperationId: false' in str(response.data)

        app.config['SWAGGER_UI_OPERATION_ID'] = False
        response = await client.get(url_for('doc'))
        assert 'displayOperationId: false' in str(response.data)

        app.config['SWAGGER_UI_OPERATION_ID'] = True
        response = await client.get(url_for('doc'))
        assert 'displayOperationId: true' in str(response.data)

    async def test_apidoc_doc_display_request_duration(self, app, client):
        sanic_restplus.Api(app)

        response = await client.get(url_for('doc'))
        assert 'displayRequestDuration: false' in str(response.data)

        app.config['SWAGGER_UI_REQUEST_DURATION'] = False
        response = await client.get(url_for('doc'))
        assert 'displayRequestDuration: false' in str(response.data)

        app.config['SWAGGER_UI_REQUEST_DURATION'] = True
        response = await client.get(url_for('doc'))
        assert 'displayRequestDuration: true' in str(response.data)

    async def test_custom_apidoc_url(self, app, client):
        sanic_restplus.Api(app, version='1.0', doc='/doc/')

        doc_url = url_for('doc')
        root_url = url_for('root')

        assert doc_url != root_url

        response = await client.get(root_url)
        assert response.status_code == 404

        assert doc_url == '/doc/'
        response = await client.get(doc_url)
        assert response.status_code == 200
        assert response.content_type == 'text/html; charset=utf-8'

    def test_custom_api_prefix(self, app, client):
        prefix = '/api'
        api = sanic_restplus.Api(app, prefix=prefix)
        api.namespace('resource')
        assert url_for('root') == prefix

    async def test_custom_apidoc_page(self, app, client):
        api = sanic_restplus.Api(app, version='1.0')
        content = 'My Custom API Doc'

        @api.documentation
        def api_doc():
            return content

        response = await client.get(url_for('doc'))
        assert response.status_code == 200
        assert response.data.decode('utf8') == content

    async def test_custom_apidoc_page_lazy(self, app, client):
        blueprint = Blueprint('api', __name__, url_prefix='/api')
        api = sanic_restplus.Api(blueprint, version='1.0')
        content = 'My Custom API Doc'

        @api.documentation
        def api_doc():
            return content

        app.register_blueprint(blueprint)

        response = await client.get(url_for('api.doc'))
        assert response.status_code == 200
        assert response.data.decode('utf8') == content

    async def test_disabled_apidoc(self, app, client):
        sanic_restplus.Api(app, version='1.0', doc=False)

        with pytest.raises(BuildError):
            url_for('doc')

        response = await client.get(url_for('root'))
        assert response.status_code == 404
