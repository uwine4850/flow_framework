from dataclasses import dataclass
import cgi
from flow.routing.route import Url


@dataclass
class _FormFile:
    inputname: str
    filename: str
    filedata: bytes

    def __repr__(self):
        if self.filename:
            return f"_FormFile({self.filename})"
        else:
            return f"_FormFile({self.filedata})"


class _Form:
    _form: cgi.FieldStorage = None

    @classmethod
    def get_form(cls) -> cgi.FieldStorage:
        return cls._form

    @classmethod
    def get(cls, key, default=None) -> list[_FormFile]:
        if isinstance(cls._form[key], list):
            formfiles = []
            for i in cls._form[key]:
                formfiles.append(_FormFile(key, i.filename, i.value))
            return formfiles
        else:
            return [_FormFile(key, cls._form.filename, cls._form.getvalue(key, default))]

    @classmethod
    def set_form(cls, form: cgi.FieldStorage):
        cls._form = form


class Request:
    currurl = ''
    url_obj: Url = None
    response_code = 200
    slug_data = ''
    path_data = None
    aaa = '/test/'

    class FILES(_Form):
        pass

    class POST(_Form):
        pass

