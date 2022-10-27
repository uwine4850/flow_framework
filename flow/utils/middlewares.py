from flow.http.server import Request


class Middleware:
    def __init__(self, request: Request):
        self.request = request

    def after_request(self):
        pass
        # return self.request

    def before_request(self):
        pass
