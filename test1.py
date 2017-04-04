import operator

from sanic import Sanic
from sanic import response
from sanic_restplus import Resource, Api, fields
from sanic_restplus.utils import get_accept_mimetypes

from flask import Request

app = Sanic(__name__)

api = Api(app)

todos = {}


resource_fields = api.model('Resource', {
    'data': fields.String,
})

@api.route('/<todo_id:[A-z0-9]+>')
@api.doc(params={'todo_id': 'A TODO ID'})
class TodoSimple(Resource):
    """
    You can try this example as follow:
        $ curl http://localhost:5000/todo1 -d "data=Remember the milk" -X PUT
        $ curl http://localhost:5000/todo1
        {"todo1": "Remember the milk"}
        $ curl http://localhost:5000/todo2 -d "data=Change my breakpads" -X PUT
        $ curl http://localhost:5000/todo2
        {"todo2": "Change my breakpads"}

    Or from python if you have requests :
     >>> from requests import put, get
     >>> put('http://localhost:5000/todo1', data={'data': 'Remember the milk'}).json
     {u'todo1': u'Remember the milk'}
     >>> get('http://localhost:5000/todo1').json
     {u'todo1': u'Remember the milk'}
     >>> put('http://localhost:5000/todo2', data={'data': 'Change my breakpads'}).json
     {u'todo2': u'Change my breakpads'}
     >>> get('http://localhost:5000/todo2').json
     {u'todo2': u'Change my breakpads'}

    """
    def get(self, request, todo_id):
        return {todo_id: todos[todo_id]}

    @api.expect(resource_fields)
    def put(self, request, todo_id):

        todos[todo_id] = request.form['data']
        return {todo_id: todos[todo_id]}

if __name__ == '__main__':
    app.run(port=8001, debug=True)


