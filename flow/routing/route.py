from dataclasses import dataclass
from flow.exceptions.http_exceptions import RedirectError


class Url:
    def __init__(self, path: str, handler, name: str, slug_value: str = None):
        # self.path = path
        self.path: _ParsePathData = Route.parse_path(path)
        self.handler = handler
        self.name = name
        self.slug_value = slug_value
        self.header = ()
        self.code = None
        self.redirect: bool = False


class RedirectUrl:
    """
    Redirect to selected url.
    """
    def __init__(self, urlname, **kwargs):
        from fconfig.froute import routings
        self.u: Url = None
        for route in routings:
            if route.name == urlname:
                # path = Route.parse_path(route.path)
                # self.u = Url(route.path, route.handler, route.name)
                self.u = Url(route.path.path, route.handler, route.name)
                # self.u.header = ('Content-type', '')
                if 'slug_value' in kwargs.keys():
                    self.u.slug_value = kwargs['slug_value']
                    self.u.header = ('Location', route.path.path.replace(route.path.slug_f, str(self.u.slug_value)))
                else:
                    self.u.header = ('Location', route.path.path)
                self.u.code = 303
                self.u.redirect = True
        if not self.u:
            raise RedirectError(urlname)

    def redirect(self) -> Url:
        return self.u


class Route:
    _urls = []

    @classmethod
    def url(cls, path: str, handler, name: str) -> Url:
        u = Url(path, handler, name)
        u.header = ('Content-type', 'a')
        u.code = 200
        return u

    @staticmethod
    def parse_path(path: str):
        slug_f = ''
        left_c = path.find('[')
        right_c = path.find(']')+1
        if left_c != -1:
            slug_f = path[left_c:right_c:]
        return _ParsePathData(path, left_c, slug_f)


@dataclass
class _ParsePathData:
    path: str
    left_c: int
    slug_f: str
