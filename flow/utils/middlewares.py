from flow.http.request import Request
from flow.routing.route import RedirectUrl


class Middleware:
    def __init__(self, request: Request):
        self.request = request

    def after_request(self):
        pass
        # return self.request

    def before_request(self):
        pass

    def redirect(self, urlname, slug_value=None):
        if slug_value:
            return RedirectUrl(urlname, slug_value=slug_value).redirect()
        else:
            return RedirectUrl(urlname).redirect()
