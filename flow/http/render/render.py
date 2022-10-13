from fconfig.fsettings import TEMPLATES_PATH
import jinja2
import os
from fconfig.fsettings import TEMPLATE_EXTENSION_RELATIVE_PATH, GLOBAL_OBJ_PATH
import importlib
from flow.http.render.templ_extension import BaseExtension
from typing import Type


class RenderPage:
    def __init__(self, template: str):
        self._tempalate = template
        self._functions = []

    def set_template_functions(self, functions: list[callable]):
        self._functions = functions
        return self

    def render(self, **kwargs) -> str:
        for templ in TEMPLATES_PATH:
            filepath = os.path.join(templ, self._tempalate)
            if os.path.exists(filepath):
                filename = filepath[filepath.rfind('/') + 1::]
                return _JinjaInit(filepath, filename).template_functions(self._functions).jinit(**kwargs)
        raise 'Template not found.'


class _JinjaInit:
    def __init__(self, filepath: str, filename: str):
        self._path = filepath
        self._env = jinja2.Environment(loader=self._get_loader(), extensions=self._get_extensons())
        self._template = self._env.get_template(filename)
        self._template_obj = []

    def template_functions(self, functions: list[callable]):
        for func in functions:
            funcname = func.__name__
            self._env.globals[funcname] = func
        return self

    def _get_loader(self) -> jinja2.ChoiceLoader:
        """
        Creates loaders for html templates.
        """
        fsl = []
        for template in TEMPLATES_PATH:
            fsl.append(jinja2.FileSystemLoader(template))
        loader = jinja2.ChoiceLoader(fsl)
        return loader

    def _get_extensons(self) -> list[Type[BaseExtension]]:
        """
        Collects all template extensions (Classes) inherited from BaseExtension.
        :return:
        """
        for path in TEMPLATE_EXTENSION_RELATIVE_PATH:
            p = path.replace('/', '.')
            importlib.import_module(f'{p}template_ext')
        return BaseExtension.__subclasses__()

    def _set_global_obj(self):
        for path in GLOBAL_OBJ_PATH:
            p = path.replace('/', '.')
            importlib.import_module(f'{p}global_obj')
            gtos = GlobalTemplateObject.__subclasses__()

        for gto in gtos:
            g = gto()
            self._template_obj = g.objects
            self.template_functions(g.functions)

    def jinit(self, **kwargs):
        self._set_global_obj()
        for obj in self._template_obj:
            kwargs[obj] = self._template_obj[obj]
        render = self._template.render(kwargs)
        return render


class GlobalTemplateObject:
    """
    The class that contains all the global template attributes.
    """
    def __init__(self):
        self.objects = []
        self.functions = []

    def add_object(self, **kwargs):
        self.objects = kwargs

    def add_function(self, func: callable):
        self.functions.append(func)
