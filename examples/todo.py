from sanic import Sanic

from sanic_restplus import Api, fields, Resource
from sanic_restplus.restplus import restplus
from spf import SanicPluginsFramework
app = Sanic(__name__)
spf = SanicPluginsFramework(app)
rest_assoc = spf.register_plugin(restplus)

api = Api(version='1.0', title='Todo API',
          description='A simple TODO API')

ns = api.namespace('todos', description='TODO operations')

TODOS = {
    'todo1': {'task': 'build an API'},
    'todo2': {'task': '?????'},
    'todo3': {'task': 'profit!'},
}

todo = api.model('Todo', {
    'task': fields.String(required=True, description='The task details')
})

listed_todo = api.model('ListedTodo', {
    'id': fields.String(required=True, description='The todo ID'),
    'todo': fields.Nested(todo, description='The Todo')
})


def abort_if_todo_doesnt_exist(todo_id):
    if todo_id not in TODOS:
        api.abort(404, "Todo {} doesn't exist".format(todo_id))

parser = api.parser()
parser.add_argument('task', type=str, required=True, help='The task details', location='form')


@ns.route('/<todo_id>')
@api.doc(responses={404: 'Todo not found'}, params={'todo_id': 'The Todo ID'})
class Todo(Resource):
    '''Show a single todo item and lets you delete them'''
    @api.doc(description='todo_id should be in {0}'.format(', '.join(TODOS.keys())))
    @api.marshal_with(todo)
    async def get(self, request, todo_id, context):
        '''Fetch a given resource'''
        abort_if_todo_doesnt_exist(todo_id)
        return TODOS[todo_id]

    @api.doc(responses={204: 'Todo deleted'})
    def delete(self, request, todo_id):
        '''Delete a given resource'''
        abort_if_todo_doesnt_exist(todo_id)
        del TODOS[todo_id]
        return '', 204

    @api.doc(parser=parser)
    @api.marshal_with(todo)
    def put(self, request, context, todo_id):
        '''Update a given resource'''
        req_context = context['request'][id(request)]
        args = parser.parse_args(request, req_context)
        task = {'task': args['task']}
        TODOS[todo_id] = task
        return task


@ns.route('/')
class TodoList(Resource):
    '''Shows a list of all todos, and lets you POST to add new tasks'''
    @api.marshal_list_with(listed_todo)
    async def get(self, request, context):
        '''List all todos'''
        return [{'id': id, 'todo': todo} for id, todo in TODOS.items()]

    @api.doc(parser=parser)
    @api.marshal_with(todo, code=201)
    async def post(self, request, context=None):
        '''Create a todo'''
        req_context = context['request'][id(request)]
        args = parser.parse_args(request, req_context)
        todo_id = 'todo%d' % (len(TODOS) + 1)
        TODOS[todo_id] = {'task': args['task']}
        return TODOS[todo_id], 201

rest_assoc.api(api)

if __name__ == '__main__':
    app.run(debug=True, auto_reload=False)
