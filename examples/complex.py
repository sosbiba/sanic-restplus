from sanic import Sanic
from sanic_restplus.restplus import restplus
from spf import SanicPluginsFramework
from examples.zoo import api

app = Sanic(__name__)
spf = SanicPluginsFramework(app)
rest_assoc = spf.register_plugin(restplus)
rest_assoc.api(api)

app.run(debug=True)
