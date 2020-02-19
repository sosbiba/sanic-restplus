# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import sanic_restplus
from sanic_restplus import restplus
from sanic.response import HTTPResponse

class Foo(sanic_restplus.Resource):
    async def get(self, request):
        return "data", 200


class ErrorsTest(object):
    async def test_accept_default_application_json(self, app, client):
        api = sanic_restplus.Api(app)
        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers={'Accept': ''})
        assert res.status == 200
        assert res.content_type == 'application/json'

    async def test_accept_application_json_by_default(self, app, client):
        api = sanic_restplus.Api(app)
        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'application/json')])
        assert res.status == 200
        assert res.content_type == 'application/json'

    async def test_accept_no_default_match_acceptable(self, app, client):
        api = sanic_restplus.Api(app, default_mediatype=None)
        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'application/json')])
        assert res.status == 200
        assert res.content_type == 'application/json'

    async def test_accept_default_override_accept(self, app, client):
        api = sanic_restplus.Api(app)
        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'text/plain')])
        assert res.status == 200
        assert res.content_type == 'application/json'

    async def test_accept_default_any_pick_first(self, app, client):
        api = sanic_restplus.Api(app)

        @api.representation('text/plain')
        def text_rep(data, status_code, headers=None):
            resp = HTTPResponse(str(data), status_code, headers)
            return resp

        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', '*/*')])
        assert res.status == 200
        assert res.content_type == 'application/json'

    async def test_accept_no_default_no_match_not_acceptable(self, app, client):
        api = sanic_restplus.Api(app, default_mediatype=None)
        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'text/plain')])
        assert res.status == 406
        assert res.content_type == 'application/json'

    async def test_accept_no_default_custom_repr_match(self, app, client):
        api = sanic_restplus.Api(app, default_mediatype=None)
        api.representations = {}

        @api.representation('text/plain')
        def text_rep(request, data, status_code, headers=None):
            resp = HTTPResponse(str(data), status_code, headers)
            return resp

        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'text/plain')])
        assert res.status == 200
        assert res.content_type == 'text/plain'

    async def test_accept_no_default_custom_repr_not_acceptable(self, app, client):
        api = sanic_restplus.Api(app, default_mediatype=None)
        api.representations = {}

        @api.representation('text/plain')
        def text_rep(request, data, status_code, headers=None):
            resp = HTTPResponse(str(data), status_code, headers)
            return resp

        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'application/json')])
        assert res.status == 406
        assert res.content_type == 'text/plain'

    async def test_accept_no_default_match_q0_not_acceptable(self, app, client):
        """
        q=0 should be considered NotAcceptable,
        """
        api = sanic_restplus.Api(app, default_mediatype=None)
        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'application/json; q=0')])
        assert res.status == 406

    async def test_accept_no_default_accept_highest_quality_of_two(self, app, client):
        api = sanic_restplus.Api(app, default_mediatype=None)

        @api.representation('text/plain')
        def text_rep(request, data, status_code, headers=None):
            resp = HTTPResponse(str(data), status_code, headers)
            return resp

        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'application/json; q=0.1, text/plain; q=1.0')])
        assert res.status == 200
        assert res.content_type == 'text/plain'

    async def test_accept_no_default_accept_highest_quality_of_three(self, app, client):
        api = sanic_restplus.Api(app, default_mediatype=None)

        @api.representation('text/html')
        @api.representation('text/plain')
        def text_rep(request, data, status_code, headers=None):
            resp = HTTPResponse(str(data), status_code, headers)
            return resp

        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'application/json; q=0.1, text/plain; q=0.3, text/html; q=0.2')])
        assert res.status == 200
        assert res.content_type == 'text/plain'

    async def test_accept_no_default_no_representations(self, app, client):
        api = sanic_restplus.Api(app, default_mediatype=None)
        api.representations = {}

        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'text/plain')])
        assert res.status == 406
        assert res.content_type == 'text/plain'

    async def test_accept_invalid_default_no_representations(self, app, client):
        api = sanic_restplus.Api(app, default_mediatype='nonexistant/mediatype')
        api.representations = {}

        api.add_resource(Foo, '/test/')

        res = await client.get('/test/', headers=[('Accept', 'text/plain')])
        assert res.status == 500
