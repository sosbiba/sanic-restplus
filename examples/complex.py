from sanic import Sanic

from examples.zoo import api

app = Sanic(__name__)

api.init_app(app)

app.run(debug=True)
