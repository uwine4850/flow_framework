from http.server import CGIHTTPRequestHandler
import fconfig
import os
import cgi
from dataclasses import dataclass
from flow.routing.route import Route, Url
from flow.exceptions.http_exceptions import FormEnctypeError, MimetypeError

import importlib


MIMETYPES = {
    'text/html': 'html',
    'text/css': 'css',
    'image/jpeg': 'jpg, jpeg',
    'text/javascript': '.js'
}


class Server(CGIHTTPRequestHandler):
    middlewares = []

    def do_GET(self):
        self.get_middlewares()
        if self.path.rfind('.') != -1:
            mimetype = self._get_mimetype()
            path = self.path.split(Request.currurl)[-1]
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    file = f.read()
                self._write_file(file, mimetype, 200, ('Content-Type', ''))
        else:
            self._route()

    def do_POST(self) -> None:
        self.get_middlewares()
        ctype, pdict = cgi.parse_header(self.headers.get('Content-Type'))
        match ctype:
            case 'multipart/form-data':
                pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
                Request.FILES.set_form(self._get_form())
            case 'application/x-www-form-urlencoded':
                Request.POST.set_form(self._get_form())
            case _:
                raise FormEnctypeError(ctype)
        self._route_post()

    def _get_form(self):
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers['Content-Type']}
        )
        return form

    def _write_file(self, templatefile: bytes, mimetype: str, code: int, header: iter):
        self.send_response(code)
        if header[0] == 'Content-type':
            self.send_header('Content-type', mimetype)
        else:
            self.send_header(header[0], header[1])
        self.end_headers()
        self.wfile.write(templatefile)

    def _get_mimetype(self):
        if self.path.rfind('.') != -1:
            filetype = self.path.rsplit('.')[1]
            for mtype in MIMETYPES:
                if filetype in MIMETYPES[mtype]:
                    return mtype
                if filetype == 'ico':
                    return
            raise MimetypeError(filetype)

    def _route(self):
        page_found = False
        for url in fconfig.froute.routings:
            path_data, url_path, slug_data = self._parse_path(url)
            if self.path == url_path:
                page_found = True
                mimetype = self._get_mimetype()
                Request.currurl = self.path
                self.run_before_middlewares()
                if slug_data:
                    Request.slug_data = {path_data.slug_f.strip('[').strip(']'): slug_data}
                    self._write_file(bytes(url.handler(request=Request, slug_value=slug_data), 'utf-8'), mimetype,
                                     url.code, url.header)
                else:
                    self._write_file(bytes(url.handler(request=Request), 'utf-8'), mimetype, url.code, url.header)
                self.run_after_middlewares()
        if not page_found:
            self.send_error(404, 'Page not found')

    def _route_post(self):
        page_found = False
        for url in fconfig.froute.routings:
            path_data, url_path, slug_data = self._parse_path(url)
            if self.path == url_path:
                page_found = True
                redirect_url: Url = url.handler.post()
                path_data, url_path, slug_data = self._parse_path(redirect_url)
                Request.currurl = url_path
                self.run_before_middlewares()
                if slug_data:
                    Request.slug_data = {path_data.slug_f.strip('[').strip(']'): slug_data}
                    self._write_file(bytes(redirect_url.handler(request=Request, slug_value=slug_data), 'utf-8'), '',
                                     redirect_url.code, redirect_url.header)
                else:
                    self._write_file(bytes(redirect_url.handler(request=Request), 'utf-8'), '', redirect_url.code,
                                     redirect_url.header)
                self.run_after_middlewares()
        if not page_found:
            self.send_error(404, 'Page not found')

    def _parse_path(self, urlobj: Url):
        path_data = Route.parse_path(urlobj.path)
        url_path = urlobj.path
        slug_data = ''
        if path_data.slug_f:
            slug_data = self.path[path_data.left_c::]
            slug_data = slug_data.split('/')[0]
            url_path = path_data.path.replace(path_data.slug_f, slug_data)
        return path_data, url_path, slug_data

    def get_middlewares(self):
        from flow.utils.middlewares import Middleware
        for mddl_path in fconfig.fsettings.MIDDLEWARES_PATH:
            for mddl_name in fconfig.fsettings.MIDDLEWARES:
                if os.path.exists(os.path.join(mddl_path, mddl_name+'.py')):
                    importlib.import_module(f'{mddl_path.replace("/", ".")}{mddl_name}')
                    for i in Middleware.__subclasses__():
                        if not i in self.middlewares:
                            self.middlewares.append(i)

    def run_before_middlewares(self):
        for mddl in self.middlewares:
            mddl(Request).before_request()

    def run_after_middlewares(self):
        for mddl in self.middlewares:
            mddl(Request).after_request()


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
    url = ''
    response_code = 200
    slug_data = {}

    class FILES(_Form):
        pass

    class POST(_Form):
        pass
