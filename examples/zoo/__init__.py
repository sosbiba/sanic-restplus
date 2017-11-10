from sanic_restplus import Api

from .cat import api as cat_api
from .dog import api as dog_api

api = Api(
    title='Zoo API',
    version='1.0',
    description='A simple demo API',
    additional_css="/static/testme.css"
)

api.add_namespace(cat_api)
api.add_namespace(dog_api)
