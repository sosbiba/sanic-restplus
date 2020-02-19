# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from sanic_restplus import Api, Resource, cors


class ErrorsTest(object):
    async def test_crossdomain(self, app, client):
        class Foo(Resource):
            @cors.crossdomain(origin='*')
            async def get(self, request):
                return "data", 200

        api = Api(app)
        api.add_resource(Foo, '/test/')

        res = await client.get('/test/')
        assert res.status == 200
        assert res.headers['Access-Control-Allow-Origin'] == '*'
        assert res.headers['Access-Control-Max-Age'] == '21600'
        assert 'HEAD' in res.headers['Access-Control-Allow-Methods']
        assert 'OPTIONS' in res.headers['Access-Control-Allow-Methods']
        assert 'GET' in res.headers['Access-Control-Allow-Methods']

    async def test_access_control_expose_headers(self, app, client):
        class Foo(Resource):
            @cors.crossdomain(origin='*',
                              expose_headers=['X-My-Header', 'X-Another-Header'])
            async def get(self, request):
                return "data", 200

        api = Api(app)
        api.add_resource(Foo, '/test/')

        res = await client.get('/test/')
        assert res.status == 200
        assert 'X-MY-HEADER' in res.headers['Access-Control-Expose-Headers']
        assert 'X-ANOTHER-HEADER' in res.headers['Access-Control-Expose-Headers']

    async def test_no_crossdomain(self, app, client):
        class Foo(Resource):
            async def get(self, request):
                return "data", 200

        api = Api(app)
        api.add_resource(Foo, '/test/')

        res = await client.get('/test/')
        assert res.status == 200
        assert 'Access-Control-Allow-Origin' not in res.headers
        assert 'Access-Control-Allow-Methods' not in res.headers
        assert 'Access-Control-Max-Age' not in res.headers
