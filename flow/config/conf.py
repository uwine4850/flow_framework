from flow.config.templates import fsettings, froute, models, views
from dataclasses import dataclass


@dataclass
class TemplateFile:
    dirname: str
    filename: str
    filepath: str


PROJECT_FILES: list[TemplateFile] = [
    TemplateFile('fconfig', 'fsettings.py', fsettings.__file__),
    TemplateFile('fconfig', 'froute.py', froute.__file__),
]

APP_FILES: list[TemplateFile] = [
    TemplateFile('', 'models.py', models.__file__),
    TemplateFile('', 'views.py', views.__file__),
    TemplateFile('', '__init__.py', ''),
]
