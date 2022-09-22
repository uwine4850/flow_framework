from enum import Enum
import importlib
from fconfig.fsettings import APPS
from flow.config.conf import DefTableName, DEFAULT_TABLES
import os
import datetime
from typing import Type
from flow.exceptions.migrate_exceptions import ErrorWritingToFile, ErrorAddingTableToLog, ErrorAddingFieldToLog,\
    ErrorUpdateFieldInLog, ErrorDeleteFieldInLog, ErrorDeleteTableInLog, ErrorValidation


class FieldType(Enum):
    INT = 'INT'
    FK = 'FK'


class FieldAction(Enum):
    DELETE = 'DELETE'
    UPDATE = 'UPDATE'
    CREATE = 'CREATE'
    NOACTION = 'NOACTION'


class Model:
    def init_model(self):
        self._set_fields_name()
        return self.__class__

    def get_fields(self):
        return [self.__class__.__dict__[i] for i in self.__class__.__dict__ if not i.endswith('__') and not i.startswith('__')]

    def _set_fields_name(self):
        fieldsname = [i for i in self.__class__.__dict__ if not i.endswith('__') and not i.startswith('__')]
        for fieldname in fieldsname:
            self.__class__.__dict__[fieldname].set_fname(fieldname)


class _Field:
    def __init__(self):
        self.fname: str = ''
        self.ftype: FieldType = None
        self.flength: int = 0
        self.fk: str = None
        self.fnull: bool = None
        self.action: FieldAction = None

    def get_strbuild(self) -> str:
        pass

    def set_action(self, action: FieldAction):
        self.action = action
        return self

    def set_fname(self, fname: str):
        self.fname = fname
        return self

    @staticmethod
    def fnull_to_sql_bollean(fnull):
        if fnull:
            return 1
        else:
            return 0


class ForeignKey(_Field):
    def __init__(self, fk: str,  fnull: bool = False):
        super().__init__()
        self.ftype = FieldType.FK
        self.fk = fk
        self.fnull = fnull

    def get_strbuild(self) -> str:
        if self.fk:
            return f"ForeignKey(fk='{self.fk}', fnull={self.fnull})"
        else:
            return f'ForeignKey(fnull={self.fnull})'


class IntField(_Field):
    def __init__(self, flength: int = 0, fnull: bool = False):
        super().__init__()
        self.ftype = FieldType.INT
        self.flength = flength
        self.fnull = fnull

    def get_strbuild(self) -> str:
        if self.flength:
            return f'IntField(flength={self.flength}, fnull={self.fnull})'
        else:
            return f'IntField(fnull={self.fnull})'


class DelField(_Field):
    def __init__(self):
        super().__init__()
        self.action = FieldAction.DELETE

    def get_strbuild(self) -> str:
        return f"DelField()"


class _UndefinedField(_Field):
    def __init__(self):
        super().__init__()
        self.fk = None


class MigrateModel:
    # simple table

    default_fields = [

    ]
    action: FieldAction = None
    name: str = ''
    fields: list[_Field] = [

    ]

    def new_instance(self, name: str, fields: list[_Field] = None):
        self.name = name
        if fields:
            self.fields = fields
        return self


class Migrate:
    """
    Головний клас міграцій. Клас запускає усі потрібні компоненти для запису міграцій.
    """
    def __init__(self, models_dict: dict[str, list[Type[Model]]]):
        from flow.database.query import DbQuery

        self._query = DbQuery()
        self.models_dict = models_dict
        self.mgr_file_paths: dict[str] = {}
        self.files = []
        self._migrate_apps()

    def _migrate_apps(self):
        """
        Метод запускає усі потрібні молулі для виконання міграцій.
        """

        # check default tables
        for dtab in DEFAULT_TABLES:
            if not dtab in self._query.show_tables():
                for query in DEFAULT_TABLES[dtab]:
                    self._query.custom_query(query)

        # init models
        for key in self.models_dict:
            for model in self.models_dict[key]:
                model().init_model()

        self._create_mgr_dirs()
        applylog = DbFMgrApplyLog()

        for app in self.mgr_file_paths:
            filename = f"mgr_{datetime.datetime.now().strftime('%y_%m_%d__%H_%M_%S')}.py"
            filepath = os.path.join(self.mgr_file_paths[app], filename)
            path, dirs, files = next(os.walk(self.mgr_file_paths[app]))
            self.files = files

            # якщо файли міграцій не знайдені.
            if not files:
                for model in self.models_dict[app]:
                    migrate_model = MigrateModel().new_instance(model.__name__.lower(), model().get_fields())
                    CreateMgrFramework(model=migrate_model, filepath=filepath, filename=filename, first_mgr=True)\
                        .set_default_fields([IntField().set_fname('id').set_action(FieldAction.CREATE)])\
                        .create()
                applylog.append_table_in_log(app, filename)

        # якщо файли міграцій знайдені.
        if self.files:

            # валідація створених моделей.
            models = []
            for mapp in self.models_dict:
                for model in self.models_dict[mapp]:
                    models.append(model)
            mgr_models = _MigrateValidation(models).validate().get_validate_models()

            if not mgr_models:
                print('No mgr_models')
            else:
                applylog.clear_table_data()

            # створення нових файлів міграцій на основі валідації.
            for app in self.mgr_file_paths:
                filename = f"mgr_{datetime.datetime.now().strftime('%y_%m_%d__%H_%M_%S')}.py"
                filepath = os.path.join(self.mgr_file_paths[app], filename)
                for mgr_model in mgr_models:
                    if mgr_model.name in [i.__name__.lower() for i in self.models_dict[app]]:
                        CreateMgrFramework(model=mgr_model, filepath=filepath, filename=filename) \
                            .set_default_fields([IntField().set_fname('id').set_action(FieldAction.CREATE)]) \
                            .create()
                        applylog.append_table_in_log(app, filename)

            # запис в лог оновлення моделей якщо вони писутні.
            if mgr_models:
                _InsertMgrData().update_log()

        # якщо створених таблиць не знайдено, створити їх (перша міграція).
        if not self._query.select_from(DefTableName.flow_tables.value, '*'):
            _InsertMgrData().insert_tables()
            _InsertMgrData().insert_fields()

    def _create_mgr_dirs(self):
        """
        Створення директорій(migrations) для зберігання міграцій.
        """
        for key in self.models_dict:
            for model in self.models_dict[key]:
                path = self._get_mgr_path(model)
                if not os.path.exists(path):
                    os.mkdir(path)

                if os.path.exists(path):
                    self.mgr_file_paths[key] = path
                else:
                    raise 'Dir error'

    def _get_mgr_path(self, model: Type[Model]) -> str:
        return f"{model.__module__.split('.')[0]}/migrations"


class _MigrateValidation:
    """
    Валідація даних моделей.
    """
    def __init__(self, models: list[Type[Model]]):
        from flow.database.query import DbQuery

        self._query = DbQuery()
        self.migrate_models = [MigrateModel().new_instance(i.__name__.lower(), i().get_fields()) for i in models]

    def _table_validation(self):
        """
        Валідація операцій з таблицями.
        Видалення таблиць.
        """

        for m_model in self.migrate_models:
            try:
                if not m_model.name in self._query.select_from(DefTableName.flow_tables.value, 'tn'):
                    m_model.action = FieldAction.CREATE
            except Exception:
                raise ErrorValidation(f"Table creation validation error.")

        for tn in self._query.select_from(DefTableName.flow_tables.value, 'tn'):
            if not tn in [i.name for i in self.migrate_models]:
                try:
                    # створення поля для позначення видалення і mgr_models == True
                    del_mgrmodel = MigrateModel().new_instance(tn)
                    uf = _UndefinedField()
                    uf.action = _UndefinedField().set_action(FieldAction.NOACTION)
                    del_mgrmodel.fields.append(uf)
                    self.migrate_models.append(del_mgrmodel)

                    table = self._query.select_from(DefTableName.flow_tables.value, 'id, applystatus', f"tn = '{tn}'", list_format=False,
                                                    dictionary=True)[0]

                    _InsertMgrData.delete_table(table)
                except Exception:
                    raise ErrorDeleteTableInLog(tn)
                finally:
                    print(_migration_log(f" - ✔️ The table '{tn}' was successfully deleted in the log."))

    def _del_fields_validation(self):
        curfieldname = ''
        try:
            tn_ids = {}
            for tn in self._query.select_from(DefTableName.flow_tables.value, 'tn'):
                tn_ids[tn] = self._query.select_from(DefTableName.flow_tables.value, 'id', f"tn = '{tn}'")[0]

            for tn in tn_ids:
                for i in self.migrate_models:
                    if i.name == tn:
                        table_fields = self._query.select_from(DefTableName.flow_fields.value, 'fname', f"parent_table = '{tn_ids[tn]}'")
                        for tf in table_fields:
                            curfieldname = tf
                            if not tf in [j.fname for j in i.fields]:
                                i.fields.append(DelField().set_fname(tf))
        except Exception:
            raise ErrorValidation(f"Error validating deletion of field '{curfieldname}'.")

    def _create_fields_validation(self):
        curfieldname = ''
        try:
            tn_ids = {}
            for tn in self._query.select_from(DefTableName.flow_tables.value, 'tn'):
                tn_ids[tn] = self._query.select_from(DefTableName.flow_tables.value, 'id', f"tn = '{tn}'")[0]

            for model in self.migrate_models:
                for tn in tn_ids:
                    if model.name == tn:
                        for field in model.fields:
                            curfieldname = field.fname
                            flowfields = self._query.select_from(DefTableName.flow_fields.value, 'fname, action', f"parent_table = '{tn_ids[tn]}'",
                                                             list_format=False, dictionary=True)
                            if not field.fname in [i['fname'] for i in flowfields]:
                                field.action = FieldAction.CREATE
                            else:
                                for dfield in flowfields:
                                    if field.fname == dfield['fname']:
                                        if dfield['action'] == FieldAction.DELETE.value:
                                            field.action = FieldAction.CREATE
        except Exception:
            raise ErrorValidation(f"Validation failed to create field '{curfieldname}'.")

    def _update_fields_validaton(self):
        tn_ids = {}
        for tn in self._query.select_from(DefTableName.flow_tables.value, 'tn'):
            tn_ids[tn] = self._query.select_from(DefTableName.flow_tables.value, 'id', f"tn = '{tn}'")[0]

        for model in self.migrate_models:
            for tn in tn_ids:
                if model.name == tn:
                    for field in model.fields:
                        try:
                            if field.fname in self._query.select_from(DefTableName.flow_fields.value, 'fname', f"parent_table = '{tn_ids[tn]}'"):
                                field_data = self._query.custom_query(
                                    f"SELECT * FROM {DefTableName.flow_fields.value} WHERE `parent_table` = '{tn_ids[tn]}' AND "
                                    f"`fname` = '{field.fname}'", dictionary=True)[0]
                                undef_field = _UndefinedField()
                                undef_field.fname = field_data['fname']
                                undef_field.ftype = field_data['ftype']
                                undef_field.flength = field_data['flength']
                                undef_field.fnull = field_data['fnull']
                                if field_data['fk'] == 'None':
                                    undef_field.fk = None
                                else:
                                    undef_field.fk = field_data['fk']

                                field_attr = [i for i in field.__dict__]
                                field_attr.remove('fname')
                                if field_values_to_dict(field) != field_values_to_dict(undef_field):
                                    field.action = FieldAction.UPDATE
                        except Exception:
                            raise ErrorValidation(f"Error validating update of field '{field.fname}'.")

    def _filter_mgr_models(self):
        """
        Видаленя із списка моделей які не зазнали змін.
        """
        remove_fields = []
        remove_models = []
        for model in self.migrate_models:
            if not model.action:
                model.action = FieldAction.NOACTION
            for field in model.fields:
                if not field.action:
                    remove_fields.append(field)
            for r in remove_fields:
                if r in model.fields:
                    model.fields.remove(r)

            if not model.fields:
                remove_models.append(model)

        for rm in remove_models:
            self.migrate_models.remove(rm)

    def validate(self):
        self._table_validation()
        self._update_fields_validaton()
        self._create_fields_validation()
        self._del_fields_validation()
        self._filter_mgr_models()

        return self

    def get_validate_models(self) -> list[MigrateModel]:
        return self.migrate_models


class _InsertMgrData:
    """
    Клас записує лог бази даних дані про моделі, які беруться із останніх файлів міграцій.
    """
    def __init__(self):
        from flow.database.query import DbQuery

        self._query = DbQuery()
        self.migrations_dict: dict[str, list[MigrateModel]] = self._get_migrations()

    def _get_migrations(self) -> dict[str, list[MigrateModel]]:
        """
        Отримання останніх файлів міграцій.
        """
        appended_mgrmodel = []
        migrations_dict = {}
        for app in APPS:
            path, dirs, files = next(os.walk(f'{app}/migrations'))
            sorted_files = _sorted_folder_items(files)
            importlib.import_module(f'{app}.migrations.{sorted_files[0].split(".")[0]}')
            if sorted_files[0].split(".")[0] in migrations_dict.keys():
                mgrlist = list(set(MigrateModel.__subclasses__()) - set(appended_mgrmodel))
                for mgrmodel in mgrlist:
                    migrations_dict[sorted_files[0].split(".")[0]].append(mgrmodel)
                    appended_mgrmodel.append(mgrmodel)
            else:
                mgrlist = list(set(MigrateModel.__subclasses__()) - set(appended_mgrmodel))
                migrations_dict[sorted_files[0].split(".")[0]] = []
                for mgrmodel in mgrlist:
                    migrations_dict[sorted_files[0].split(".")[0]].append(mgrmodel)
                    appended_mgrmodel.append(mgrmodel)
        return migrations_dict

    def insert_tables(self):
        """
        Додавання таблиць у лог. Перша міграція.
        """
        tn = []
        sngtn = ''
        try:
            for i in self.migrations_dict:
                for mgrmodel in self.migrations_dict[i]:
                    if not mgrmodel.name in self._query.select_from(DefTableName.flow_tables.value, 'tn'):
                        tn.append(mgrmodel.name)
                        sngtn = mgrmodel.name
                        self._query.insert_data(DefTableName.flow_tables.value, insert_values_to_str(
                            tn=mgrmodel.name, action=mgrmodel.action.value))
        except Exception:
            raise ErrorAddingTableToLog(tablename=sngtn)
        finally:
            for t in tn:
                print(_migration_log(f" - ✔️ The '{t}' table has been added to the log."))

    def insert_fields(self):
        """
        Додавання атрибутів таблиць у лог. Перша міграція.
        """
        curfields = []
        sngfield = ''
        try:
            for i in self.migrations_dict:
                for mgrmodel in self.migrations_dict[i]:
                    for field in mgrmodel.fields:
                        curfields.append(field.fname)
                        sngfield = field.fname
                        parent_table_id = self._query.select_from(DefTableName.flow_tables.value, 'id', f"tn = '{mgrmodel.name}'")[0]
                        field_values_dict = field_values_to_dict(field)
                        field_values_dict['parent_table'] = parent_table_id
                        self._query.insert_data(DefTableName.flow_fields.value, insert_values_to_str(**field_values_dict))
        except Exception:
            raise ErrorAddingFieldToLog(fname=sngfield)
        finally:
            for f in curfields:
                print(_migration_log(f" -- ✔️ The '{f}' field has been added to the log."))

    def update_log(self):
        """
        Оновлення логу новими даними.
        """

        # оновлення даних про таблиці
        for mgr_filename in self.migrations_dict:
            if DbFMgrApplyLog().check_table_apply(mgr_filename):
                for mgrmodel in self.migrations_dict[mgr_filename]:
                    match mgrmodel.action:
                        case FieldAction.CREATE:
                            try:
                                self._query.insert_data(DefTableName.flow_tables.value, insert_values_to_str(tn=mgrmodel.name, action=FieldAction.CREATE.value))
                                self._insert_mgrmodel_fields_log(mgrmodel, mgrmodel.fields)
                            except Exception:
                                raise ErrorAddingTableToLog(tablename=mgrmodel.name)
                            finally:
                                print(_migration_log(f" - ✔️ The '{mgrmodel.name}' table has been added to the log."))
                        case FieldAction.NOACTION:
                            # оновлення даних про поля таблиць.
                            self._insert_mgrmodel_fields_log(mgrmodel, mgrmodel.fields)

    def _insert_mgrmodel_fields_log(self, mgrmodel: MigrateModel, fields: list[_Field]):
        """
        Оновлення полів таблиць у логу.

        :param mgrmodel: Модель міграції.
        :param fields: Поля міграції
        """
        for field in fields:
            match field.action:
                case FieldAction.CREATE:
                    try:
                        field_dict = self._get_field_dict(mgrmodel, field)
                        if field_dict:
                            field_dict = field_dict[0]
                            if field_dict and field_dict['action'] == FieldAction.DELETE.value:
                                self._change_field_action(field_dict['id'], FieldAction.CREATE)
                        else:
                            self.flow_fields_insert(mgrmodel, field)
                    except Exception:
                        raise ErrorAddingFieldToLog(fname=field.fname)
                    finally:
                        print(_migration_log(f" -- ✔️ The '{field.fname}' field has been added to the log."))
                case FieldAction.UPDATE:
                    try:
                        field_dict = self._get_field_dict(mgrmodel, field)[0]
                        field_values = field_values_to_dict(field)
                        field_dict.update(field_values)

                        # якщо action = create нiчого не змiнюеться
                        if not field_dict['applystatus']:
                            field_dict['action'] = FieldAction.CREATE.value
                        else:
                            field_dict['action'] = FieldAction.UPDATE.value
                        self._query.update_data(DefTableName.flow_fields.value, update_value_to_str(**field_dict),
                                                f"id = {field_dict['id']}")
                    except Exception:
                        raise ErrorUpdateFieldInLog(fname=field.fname)
                    finally:
                        print(_migration_log(f" -- ✔️ The field '{field.fname}' was successfully updated in the log."))
                case FieldAction.DELETE:
                    try:
                        field_dict = self._get_field_dict(mgrmodel, field)[0]
                        if field_dict['applystatus']:
                            self._change_field_action(field_dict['id'], FieldAction.DELETE)
                        else:
                            self._query.delete_field(DefTableName.flow_fields.value, f"id={field_dict['id']}")
                    except Exception:
                        raise ErrorDeleteFieldInLog(field.fname)
                    finally:
                        print(_migration_log(f" -- ✔️ The field '{field.fname}' was successfully deleted in the log."))

    def _get_field_dict(self, mgrmodel: MigrateModel, field: _Field) -> dict:
        """
        Перетворює дані MigrateModel у словник.
        """
        parent_table_id = self._query.select_from(DefTableName.flow_tables.value, 'id',
                                                  f"tn = '{mgrmodel.name}'")[0]
        field_dict: dict = self._query.select_from(DefTableName.flow_fields.value, '*',
                                                   f"`parent_table` = {parent_table_id} and "
                                                   f"fname = '{field.fname}'",
                                                   list_format=False, dictionary=True)
        return field_dict

    def _change_field_action(self, fid: int, action: FieldAction):
        self._query.update_data(DefTableName.flow_fields.value, update_value_to_str(action=action.value), f"id={fid}")

    def flow_fields_insert(self, mgrmodel: MigrateModel, field: _Field):
        """
        Створення нового поля у логу. Команда Create.
        """
        parent_table_id = self._query.select_from(DefTableName.flow_tables.value, 'id', f"tn = '{mgrmodel.name}'")[0]
        insert_values = {}
        fattrs = list(field.__dict__.keys())
        for attr in fattrs:
            if issubclass(field.__dict__[attr].__class__, Enum):
                insert_values[attr] = field.__dict__[attr].value
            elif isinstance(field.__dict__[attr], bool):
                insert_values[attr] = field.fnull_to_sql_bollean(field.__dict__[attr])
            else:
                insert_values[attr] = field.__dict__[attr]
        insert_values['parent_table'] = parent_table_id
        self._query.insert_data(DefTableName.flow_fields.value, insert_values_to_str(**insert_values))

    @staticmethod
    def delete_table(table: dict):
        # table: sql query dict
        from flow.database.query import DbQuery
        _query = DbQuery()

        if table['applystatus']:
            _query.update_data(DefTableName.flow_tables.value, update_value_to_str(action=FieldAction.DELETE.value),
                                    f"`id` = {table['id']}")
        else:
            _query.delete_field(DefTableName.flow_tables.value, f"`id` = {table['id']}")


class CreateMgrFramework:
    """
    Створеня файлу міграцій.
    """
    def __init__(self, model: Type[MigrateModel], filepath: str, filename: str, first_mgr: bool = False):
        from flow.database.query import DbQuery

        self.model = model
        if first_mgr:
            self.model.action = FieldAction.CREATE
        self.first_mgr = first_mgr
        self.filepath = filepath
        self.filename = filename
        self.default_fields: list[_Field] = []
        self._query = DbQuery()

    def set_default_fields(self, fields: list[_Field]):
        for field in fields:
            self.default_fields.append(field)
        return self

    def _get_default_fields(self):
        fields_str = ''
        for x, field in enumerate(self.default_fields):
            if x == 0:
                fields_str += f"models2.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models2.{field.action}),\n"
            else:
                fields_str += f"        models2.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models2.{field.action}),\n"
        return fields_str

    def _get_model_fields(self):
        fields_str = ''
        for x, field in enumerate(self.model.fields):
            if x == 0:
                if self.first_mgr:
                    fields_str += f"models2.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models2.{FieldAction.CREATE}),\n"
                else:
                    fields_str += f"models2.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models2.{field.action}),\n"
            else:
                if self.first_mgr:
                    fields_str += f"\t\tmodels2.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models2.{FieldAction.CREATE}),\n"
                else:
                    fields_str += f"\t\tmodels2.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models2.{field.action}),\n"
        return fields_str

    def _build_str_migrate_model(self, model_name, default_fields: str, model_fields: str, action: FieldAction) -> str:
        str_migrate_model = f"""\n
class Mgr{model_name}(models2.MigrateModel):
    # simple table

    default_fields = [
        {default_fields}
    ]   
    action = models2.{action}
    name = '{model_name}'
    fields = [
        {model_fields}
    ]
    """
        return str_migrate_model

    def create(self):
        try:
            with open(self.filepath, 'a') as f:
                # перевірка файла на пустоту
                if os.stat(self.filepath).st_size == 0:
                    f.write("from flow.database import models2\n")

                f.write(self._build_str_migrate_model(self.model.name, self._get_default_fields(),
                                                      self._get_model_fields(), self.model.action))
        except Exception:
            raise ErrorWritingToFile(filepath=self.filepath)


class DbFMgrApplyLog:
    def __init__(self):
        from flow.database.query import DbQuery

        self._query = DbQuery()

    def clear_table_data(self):
        self._query.clear_table(DefTableName.appaply.value)

    def check_table_apply(self, filename: str) -> bool:
        if not self._get_table_log():
            return False
        if filename.split('.')[0] in [i['filename'] for i in self._get_table_log()]:
            return True
        else:
            return False

    def append_table_in_log(self, appname: str, filename: str):
        self._query.custom_query(f"INSERT INTO `{DefTableName.appaply.value}` (`appname`, `filename`) VALUES ('{appname}', '{filename.split('.')[0]}')",
                                 dictionary=True)

    def _get_table_log(self) -> list:
        return self._query.custom_query(f'SELECT * FROM `{DefTableName.appaply.value}`', dictionary=True)

    def change_apply_status(self, filename: str, apply_value: bool):
        if apply_value:
            apply = 1
        else:
            apply = 0
        self._query.custom_query(f"UPDATE `{DefTableName.appaply.value}` SET `apply` = '{apply}' WHERE "
                                 f"`{DefTableName.appaply.value}`.`filename` = '{filename}'")


def fields_to_sql(fields: list[_Field] | _Field, brackets: bool = True):
    if brackets:
        fields_str = '( '
    else:
        fields_str = ''
    if isinstance(fields, list):
        for x, field in enumerate(fields):
            if field.fnull:
                nullstr = 'NULL'
            else:
                nullstr = 'NOT NULL'
            if x == len(fields) - 1:
                if brackets:
                    fields_str += f'`{field.fname}` {field.ftype.value} {nullstr} )'
                else:
                    fields_str += f'`{field.fname}` {field.ftype.value} {nullstr}'
            else:
                fields_str += f'`{field.fname}` {field.ftype.value} {nullstr}, '
    else:
        if fields.fnull:
            nullstr = 'NULL'
        else:
            nullstr = 'NOT NULL'
        if brackets:
            fields_str += f'`{fields.fname}` {fields.ftype.value} {nullstr} )'
        else:
            fields_str += f'`{fields.fname}` {fields.ftype.value} {nullstr}'
    return fields_str


def _sorted_folder_items(files: list):
    return sorted(files, key=lambda x: int(''.join(filter(str.isdigit, x))))[::-1]


def insert_values_to_str(**kwargs) -> str:
    fnames = '('
    for x, fname in enumerate(kwargs.keys()):
        if x == len(kwargs.keys()) - 1:
            fnames += f'`{fname}`)'
        else:
            fnames += f'`{fname}`, '

    fvalues = ' VALUES ('

    values = [kwargs[i] for i in kwargs]
    for x, val in enumerate(values):
        if x == len(kwargs.keys()) - 1:
            fvalues += f"'{val}')"
        else:
            fvalues += f"'{val}', "

    return fnames + fvalues


def update_value_to_str(**kwargs) -> str:
    values = ''
    for x, val in enumerate(kwargs.keys()):
        if x == len(kwargs.keys()) - 1:
            values += f"`{val}` = '{kwargs[val]}'"
        else:
            values += f"`{val}` = '{kwargs[val]}', "
    return values


def field_values_to_dict(field: _Field) -> dict:
    fattrs = list(field.__dict__.keys())
    field_values = {}
    for attr in fattrs:
        if issubclass(field.__dict__[attr].__class__, Enum):
            field_values[attr] = field.__dict__[attr].value
        elif isinstance(field.__dict__[attr], bool):
            field_values[attr] = field.fnull_to_sql_bollean(field.__dict__[attr])
        else:
            field_values[attr] = field.__dict__[attr]

    return field_values


def _migration_log(msg: str) -> str:
    return msg
