from flow.exceptions.base import FlowException


class FormEnctypeError(FlowException):
    def __init__(self, enct: str):
        self.msg = f"No handler found for enctype '{enct}' form."
        super(FormEnctypeError, self).__init__(self.msg)


class MimetypeError(FlowException):
    def __init__(self, mimetype: str):
        self.msg = f"Mimetype '{mimetype}' was not found in the list."
        super(MimetypeError, self).__init__(self.msg)


class RedirectError(FlowException):
    def __init__(self, path: str):
        self.msg = f"Redirect url '{path}' not found."
        super(RedirectError, self).__init__(self.msg)
