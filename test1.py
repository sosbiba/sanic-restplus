from sanic import Sanic, Blueprint
from sanic import response
from spf import SanicPluginsFramework

from sanic_restplus import restplus, Resource, Api, fields
from sanic_restplus.utils import get_accept_mimetypes
from util import ns as util_ns

app = Sanic(__name__)
bp = Blueprint("bp1", url_prefix="/bp1/")
spf_b = SanicPluginsFramework(bp)
reg = spf_b.register_plugin(restplus)
api = Api()
api.add_namespace(util_ns, "/data/v2/electrical")
reg.api(api)

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


