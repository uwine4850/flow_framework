from flow.config.templates import fsettings, froute, models, views
from fconfig.fsettings import DATABASE
from dataclasses import dataclass
from enum import Enum


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


class DefLogTable(Enum):
    appaply = '_appaply'
    flow_tables = '_flow_tables'
    flow_fields = '_flow_fields'


_appaplyquery = f"CREATE TABLE `{DATABASE['database']}`.`{DefLogTable.appaply.value}`" \
                f" ( `id` INT NOT NULL AUTO_INCREMENT, PRIMARY KEY (`id`), " \
                f" `appname` VARCHAR(300) NOT NULL ," \
                f" `filename` VARCHAR(300) NOT NULL )"

_flowtablesquery = f"CREATE TABLE `{DATABASE['database']}`.`{DefLogTable.flow_tables.value}`" \
                f" ( `id` INT NOT NULL AUTO_INCREMENT, PRIMARY KEY (`id`), " \
                f" `tn` VARCHAR(300) NOT NULL ," \
                f" `action` VARCHAR(300) NOT NULL, " \
                f" `applystatus` BOOLEAN NOT NULL DEFAULT '0' )"

_flowfieldsquery = f"CREATE TABLE `{DATABASE['database']}`.`{DefLogTable.flow_fields.value}`" \
                f" ( `id` INT NOT NULL AUTO_INCREMENT, PRIMARY KEY (`id`), " \
                f" `parent_table` INT NOT NULL ," \
                f" `fname` VARCHAR(300) NOT NULL, " \
                f" `ftype` VARCHAR(300) NOT NULL," \
                f" `fk` VARCHAR(300) NULL," \
                f" `on_delete` VARCHAR(300) NULL," \
                f" `on_update` VARCHAR(300) NULL," \
                f" `rel_name` VARCHAR(300) NULL," \
                f" `flength` INT NOT NULL," \
                f" `fnull` BOOLEAN NOT NULL," \
                f" `action` VARCHAR(300) NOT NULL, " \
                f" `applystatus` BOOLEAN NOT NULL DEFAULT '0' );" \

_flowfields_fk = f"ALTER TABLE `{DefLogTable.flow_fields.value}` ADD FOREIGN KEY (`parent_table`) REFERENCES " \
                   f"`{DefLogTable.flow_tables.value}`(`id`)" \
                   f" ON DELETE CASCADE ON UPDATE RESTRICT; "

DEFAULT_TABLES: dict[str: list] = {
    DefLogTable.appaply.value: [_appaplyquery],
    DefLogTable.flow_tables.value: [_flowtablesquery],
    DefLogTable.flow_fields.value: [_flowfieldsquery, _flowfields_fk]
}