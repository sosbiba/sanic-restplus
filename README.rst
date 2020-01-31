==============
Sanic RestPlus
==============

Sanic-RESTPlus is an extension for `Sanic`_ that adds support for quickly building REST APIs.
Sanic-RESTPlus encourages best practices with minimal setup.
If you are familiar with Sanic, Sanic-RESTPlus should be easy to pick up.
It provides a coherent collection of decorators and tools to describe your API
and expose its documentation properly using `Swagger`_.

Important Notice
================

Sanic-RestPlus version 0.4.1 (and previous versions) **does not work** on Sanic 19.12+, see this bug here: https://github.com/ashleysommer/sanicpluginsframework/issues/15

A fix is coming, but in the meantime, please use RestPlus with Sanic v19.6.3 or v19.9.0.

Compatibility
=============

Sanic-RestPlus requires Python 3.5+.
Sanic-RestPlus works with Sanic v18.12+


Installation
============

In the near future, you will be able to install Sanic-Restplus with pip:

.. code-block:: console

    $ pip install sanic-restplus

or with easy_install:

.. code-block:: console

    $ easy_install sanic-restplus


Quick start
===========

With Sanic-Restplus, you only import the api instance to route and document your endpoints.

.. code-block:: python

    from sanic import Sanic
    from sanic_restplus import Api, Resource, fields
    from sanic_restplus.restplus import restplus
    from spf import SanicPluginsFramework
    app = Sanic(__name__)
    spf = SanicPluginsFramework(app)
    rest_assoc = spf.register_plugin(restplus)

    api = Api(version='1.0', title='TodoMVC API',
              description='A simple TodoMVC API')

    ns = api.namespace('todos', description='TODO operations')

    todo = api.model('Todo', {
        'id': fields.Integer(readOnly=True, description='The task unique identifier'),
        'task': fields.String(required=True, description='The task details')
    })


    class TodoDAO(object):
        def __init__(self):
            self.counter = 0
            self.todos = []

        def get(self, id):
            for todo in self.todos:
                if todo['id'] == id:
                    return todo
            api.abort(404, "Todo {} doesn't exist".format(id))

        def create(self, data):
            todo = data
            todo['id'] = self.counter = self.counter + 1
            self.todos.append(todo)
            return todo

        def update(self, id, data):
            todo = self.get(id)
            todo.update(data)
            return todo

        def delete(self, id):
            todo = self.get(id)
            self.todos.remove(todo)


    DAO = TodoDAO()
    DAO.create({'task': 'Build an API'})
    DAO.create({'task': '?????'})
    DAO.create({'task': 'profit!'})


    @ns.route('/')
    class TodoList(Resource):
        '''Shows a list of all todos, and lets you POST to add new tasks'''

        @ns.doc('list_todos')
        @ns.marshal_list_with(todo)
        async def get(self, request):
            '''List all tasks'''
            return DAO.todos

        @ns.doc('create_todo')
        @ns.expect(todo)
        @ns.marshal_with(todo, code=201)
        async def post(self, request):
            '''Create a new task'''
            return DAO.create(request.json), 201


    @ns.route('/<id:int>')
    @ns.response(404, 'Todo not found')
    @ns.param('id', 'The task identifier')
    class Todo(Resource):
        '''Show a single todo item and lets you delete them'''

        @ns.doc('get_todo')
        @ns.marshal_with(todo)
        async def get(self, request, id):
            '''Fetch a given resource'''
            return DAO.get(id)

        @ns.doc('delete_todo')
        @ns.response(204, 'Todo deleted')
        async def delete(self, request, id):
            '''Delete a task given its identifier'''
            DAO.delete(id)
            return '', 204

        @ns.expect(todo)
        @ns.marshal_with(todo)
        async def put(self, request, id):
            '''Update a task given its identifier'''
            return DAO.update(id, request.json)

    rest_assoc.api(api)

    if __name__ == '__main__':
        app.run(debug=True, auto_reload=False)




Documentation
=============

The documentation is hosted `on Read the Docs <http://flask-restplus.readthedocs.io/en/latest/>`_
That is the Flask RestPlus documentation, the Sanic-Restplus docs are not converted yet.

.. _Sanic: https://github.com/channelcat/sanic
.. _Swagger: http://swagger.io/
