from http.server import CGIHTTPRequestHandler
import fconfig
import os
import cgi
# from dataclasses import dataclass
from flow.http.request import Request
from flow.routing.route import Route, Url
from flow.exceptions.http_exceptions import FormEnctypeError, MimetypeError
from typing import Type

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
        self.set_request()
        valid_path = ''
        slug_value = None
        page_found = False
        Request.currurl = self.path
        for url in fconfig.froute.routings:
            Request.url_obj = url
            self.run_before_middlewares()
            if Request.url_obj.redirect:
                # redirect
                if Request.url_obj.path.slug_f:
                    currpath = Request.url_obj.path.path.replace(Request.url_obj.path.slug_f,
                                                                 str(Request.url_obj.slug_value))
                    slug_value = Request.url_obj.slug_value
                    valid_path = self._start_render(currpath, slug_value)
                    if valid_path:
                        page_found = True
                        break
                else:
                    currpath = Request.url_obj.path.path
                    valid_path = self._start_render(currpath, slug_value)
                    if valid_path:
                        page_found = True
                        break
            else:
                # normal
                if Request.url_obj.path.slug_f:
                    path_data, currpath, slug_value = self._parse_path(Request.url_obj.path)
                    valid_path = self._start_render(currpath, slug_value)
                    if valid_path:
                        page_found = True
                        break
                else:
                    currpath = Request.url_obj.path.path
                    valid_path = self._start_render(currpath, slug_value)
                    if valid_path:
                        page_found = True
                        break
        if not page_found:
            self.send_error(404, 'Page not found')

    def _start_render(self, currpath, slug_value):
        ok = False
        if self.path == currpath and not Request.url_obj.redirect:
            self._render_page(Request, slug_value)
            self.run_after_middlewares()
            ok = True
        elif Request.url_obj.redirect:
            print(Request.url_obj.header)
            self._render_page(Request, slug_value)
            self.run_after_middlewares()
            ok = True
        return ok

    def _render_page(self, request: Type[Request], slug_value):
        mimetype = self._get_mimetype()
        if slug_value:
            self._write_file(bytes(request.url_obj.handler(request=request, slug_value=slug_value), 'utf-8'), mimetype,
                             request.url_obj.code, request.url_obj.header)
        else:
            self._write_file(bytes(request.url_obj.handler(request=request), 'utf-8'), mimetype,
                             request.url_obj.code, request.url_obj.header)

    def _route_post(self):
        self.set_request()
        valid_path = ''
        page_found = False
        slug_value = None
        Request.currurl = self.path
        for url in fconfig.froute.routings:
            # post return redirect object
            if url.handler.post():
                Request.url_obj = url.handler.post()
                self.run_before_middlewares()
            if Request.url_obj.redirect:
                # redirect
                if Request.url_obj.path.slug_f:
                    currpath = Request.url_obj.path.path.replace(Request.url_obj.path.slug_f,
                                                                 str(Request.url_obj.slug_value))
                    slug_value = Request.url_obj.slug_value
                    valid_path = self._start_render(currpath, slug_value)
                    if valid_path:
                        page_found = True
                        break
                else:
                    currpath = Request.url_obj.path.path
                    valid_path = self._start_render(currpath, slug_value)
                    if valid_path:
                        page_found = True
                        break
        if not page_found:
            self.send_error(404, 'Page not found')

    def _parse_path(self, urlobj):
        # path_data = Route.parse_path(urlobj.path)
        path_data = urlobj
        url_path = urlobj.path
        slug_data = ''
        if path_data.slug_f:
            slug_data = self.path[path_data.left_c::]
            slug_data = slug_data.split('/')[0]
            url_path = path_data.path.replace(path_data.slug_f, slug_data)
        elif urlobj.redirect:
            if urlobj.slug_value:
                slug_data = urlobj.slug_value
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

    def set_request(self):
        Request.currurl = self.path


# @dataclass
# class _FormFile:
#     inputname: str
#     filename: str
#     filedata: bytes
#
#     def __repr__(self):
#         if self.filename:
#             return f"_FormFile({self.filename})"
#         else:
#             return f"_FormFile({self.filedata})"
#
#
# class _Form:
#     _form: cgi.FieldStorage = None
#
#     @classmethod
#     def get_form(cls) -> cgi.FieldStorage:
#         return cls._form
#
#     @classmethod
#     def get(cls, key, default=None) -> list[_FormFile]:
#         if isinstance(cls._form[key], list):
#             formfiles = []
#             for i in cls._form[key]:
#                 formfiles.append(_FormFile(key, i.filename, i.value))
#             return formfiles
#         else:
#             return [_FormFile(key, cls._form.filename, cls._form.getvalue(key, default))]
#
#     @classmethod
#     def set_form(cls, form: cgi.FieldStorage):
#         cls._form = form
#
#
# class Request:
#     currurl = ''
#     url = ''
#     response_code = 200
#     slug_data = {}
#
#     class FILES(_Form):
#         pass
#
#     class POST(_Form):
#         pass
