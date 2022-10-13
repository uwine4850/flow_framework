class Url:
    def __init__(self, path: str, handler, name: str):
        self.path = path
        self.handler = handler
        self.name = name


class Route:
    _urls = []

    @classmethod
    def url(cls, path: str, handler, name: str) -> Url:
        return Url(path, handler, name)
