from http.server import BaseHTTPRequestHandler, CGIHTTPRequestHandler
from fconfig.froute import routings
import os


MIMETYPES = {
    'text/html': 'html',
    'text/css': 'css',
    'image/jpeg': 'jpg, jpeg'
}


class Server(CGIHTTPRequestHandler):
    def do_GET(self):
        self._route()

        if self.path.rfind('.') != -1:
            mimetype = self._get_mimetype()
            path = self.path.split(Request.currurl)[-1]
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    file = f.read()
                self._write_file(file, mimetype)

    def _write_file(self, templatefile: bytes, mimetype: str):
        self.send_response(200)
        self.send_header('Content-type', mimetype)
        self.end_headers()
        self.wfile.write(templatefile)

    def _get_mimetype(self):
        if self.path.rfind('.') != -1:
            filetype = self.path.rsplit('.')[1]
            for mtype in MIMETYPES:
                if filetype in MIMETYPES[mtype]:
                    return mtype

    def _route(self):
        for url in routings:
            if self.path == url.path:
                Request.currurl = url.path
                mimetype = self._get_mimetype()
                self._write_file(bytes(url.handler(), 'utf-8'), mimetype)


class Request:
    currurl = ''
