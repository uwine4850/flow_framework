from flow.http.render.templ_extension import BaseExtension
from fconfig.fsettings import SOURCEFILES_PATH
import os
import fconfig


class FileExt(BaseExtension):
    """
    Extensions for outputting files to html template.
    """
    tags = ['file']

    def handler(self, filepath: str):
        for path in SOURCEFILES_PATH:
            p = os.path.join(path, filepath)
            if os.path.exists(p):
                return p
            else:
                raise 'Fila not found.'


class UrlExt(BaseExtension):
    """
    Routing extensions.
    """
    tags = ['url']

    def handler(self, pathname):
        for url in fconfig.froute.routings:
            if pathname == url.name:
                return url.path
        raise 'Url not found.'
