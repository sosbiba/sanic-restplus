from sanic import Sanic, Blueprint
from spf import SanicPlugin, SanicPluginsFramework
from spf.plugin import PluginRegistration, PluginAssociated


class RestPlusAssociated(PluginAssociated):

    def api(self, *args, api_class=None, **kwargs):
        (plug, reg) = self
        return plug.api(reg, *args, api_class=api_class, **kwargs)


class RestPlus(SanicPlugin):

    AssociatedTuple = RestPlusAssociated

    def __init__(self, *args, **kwargs):
        super(RestPlus, self).__init__(*args, **kwargs)

    def __new__(cls, *args, **kwargs):
        self = super(RestPlus, cls).__new__(cls, *args, **kwargs)
        self.apis = set()
        return self

    def on_registered(self, context, reg, *args, **kwargs):
        try:
            apis = context.get('apis')
        except (LookupError, AttributeError):
            apis = None
        if apis is None:
            context['apis'] = apis = set()
        app = context.app
        try:
            ext = getattr(app, 'extensions', None)
            assert ext is not None
        except (AttributeError, AssertionError):
            setattr(app, 'extensions', dict())

    def api(self, reg, *args, api_class=None, **kwargs):
        from .api import Api
        if isinstance(reg, PluginAssociated):
            (pl, reg) = reg
            (spf, _, _) = reg
        elif isinstance(reg, PluginRegistration):
            (spf, _, _) = reg
        elif isinstance(reg, SanicPluginsFramework):
            spf = reg
            reg = self.find_plugin_registration(spf)
        elif isinstance(reg, Sanic):
            app = reg
            spf = SanicPluginsFramework(app)
            reg = self.find_plugin_registration(spf)
        else:
            raise RuntimeError("the 'reg' argument must be a SPF, an Association, Registration, or an App!")
        context = self.get_context_from_spf(reg)
        app = context.app
        assert isinstance(app, (Sanic, Blueprint))
        if api_class is None:
            if args and len(args) > 0 and isinstance(args[0], Api):
                args = list(args)
                api_class = args.pop(0)
            else:
                api_class = Api
        if isinstance(api_class, type):
            if app in args:
                # don't want app in here!
                args = list(args)
                args.remove(app)
            assert issubclass(api_class, Api)
            api = api_class(*args, **kwargs)
            kwargs = dict()
        else:
            api = api_class
        assert isinstance(api, Api)

        api.init_api(reg, **kwargs)
        context.apis.add(api)
        return api

    def register_api(self, reg, api, *args, **kwargs):
        return self.api(reg, api, *args, **kwargs)


restplus = instance = RestPlus()

__all__ = ["restplus"]
