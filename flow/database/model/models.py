from enum import Enum
import importlib
from fconfig.fsettings import APPS
from flow.config import conf as cfg
import os
import datetime
from typing import Type
from flow.exceptions.migrate_exceptions import ErrorWritingToFile, ErrorAddingTableToLog, ErrorAddingFieldToLog,\
    ErrorUpdateFieldInLog, ErrorDeleteFieldInLog, ErrorDeleteTableInLog, ErrorValidation, CreationError, ApplyValidationError
from abc import ABCMeta, abstractmethod
from flow.database.model import fields as dbfields_


class _DbConnGetData(metaclass=ABCMeta):
    @abstractmethod
    def all(self):
        pass

    @abstractmethod
    def get(self, **kwargs):
        pass


class _DbConnActionData(metaclass=ABCMeta):
    @abstractmethod
    def create(self, **kwargs):
        pass


class FkDbConnect(_DbConnGetData):
    def __init__(self, tn: str, rel_table_name: str, field_data, str_fields: list[str] = None):
        from flow.database.query import DbQuery

        self._str_fields = str_fields
        self._query = DbQuery()
        self._tn = tn
        self.rel_table_name = rel_table_name
        self.field_data = field_data

    def __repr__(self):
        return f"FkDbConnect({self._tn})"

    def all(self):
        queryset = []
        self._query.select_from(self.rel_table_name, '*', f"id = {self.field_data}")
        for field in self._query.select_from(self.rel_table_name, '*', f"id = {self.field_data}",
                                             list_format=False, dictionary=True):
            queryset.append(QuerySet(field, self.rel_table_name, self._str_fields))
        return queryset

    def get(self, **kwargs):
        key = list(kwargs.keys())[0]
        return QuerySet(self._query.select_from(self.rel_table_name, '*', f"id = {self.field_data} and {key} = {kwargs[key]}",
                                                list_format=False, dictionary=True)[0], self.rel_table_name)


class ModelDbConnect(_DbConnGetData, _DbConnActionData):
    """
    Підключення до конкретної таблиці бази даних.
    """
    def __init__(self, tn: str, str_fields: list[str]):
        from flow.database.query import DbQuery

        self._str_fields = str_fields
        self._query = DbQuery()
        self._tn = tn

    def __repr__(self):
        return f"ModelDbConnect({self._tn})"

    def all(self):
        queryset = []
        for field in self._query.select_from(self._tn, '*', list_format=False, dictionary=True):
            queryset.append(QuerySet(field, self._tn, self._str_fields))
        return queryset

    def get(self, **kwargs):
        key = list(kwargs.keys())[0]
        data = self._query.select_from(self._tn, '*', f"{key} = {kwargs[key]}", list_format=False, dictionary=True)
        if data:
            data = data[0]
        return QuerySet(data, self._tn, self._str_fields)

    def create(self, **kwargs):
        self._query.insert_data(self._tn, insert_values_to_str(**kwargs))


class QuerySet:
    """
    Результат запиту до бази даних. Представляє один рядок таблиці.
    """
    def __init__(self, field: dict, table_name: str, str_fields: list[str] = None):
        from flow.database.query import DbQuery

        self._str_fields = str_fields
        self._query = DbQuery()
        self.table_name = table_name
        self._field = field
        self._set_fields()

    def __repr__(self):
        if self._str_fields:
            fstr = f'{self.table_name}('
            for x, i in enumerate(self._str_fields):
                if x == len(self._str_fields)-1:
                    fstr += f"{i}:{str(self.__getattribute__(i))})"
                else:
                    fstr += f"{i}:{str(self.__getattribute__(i))}|"
            return f"QuerySet[{fstr}]"
        return f"QuerySet[{self.table_name}]"

    def _set_fields(self):
        for f in self._field:
            ptid = self._query.select_from(cfg.DefLogTable.flow_tables.value, 'id', f"tn = '{self.table_name}'")[0]
            ftype = self._query.select_from(cfg.DefLogTable.flow_fields.value, 'ftype, fk', f"fname = '{f}' and parent_table = {ptid}",
                                            list_format=False, dictionary=True)[0]
            if ftype['ftype'] == dbfields_.FieldType.FK.value:
                self.__setattr__(f, FkDbConnect(self.table_name, ftype['fk'], self._field[f]))
            else:
                self.__setattr__(f, self._field[f])

    def update(self, **kwargs):
        self._query.update_data(self.table_name, update_value_to_str(**kwargs), f"id={self.id}")

    def delete(self):
        self._query.delete_field(self.table_name, f"id={self.id}")


class Model:
    """
    Модель бази даних.
    """
    model_display_field: list[str] = None

    @property
    def db(self):
        return ModelDbConnect(self.__class__.__name__.lower(), self.model_display_field)

    _default_model_fields = [dbfields_.DefaultModelFields.fields]

    def set_default_fields(self, def_fields: list):
        self._default_model_fields = def_fields
        dbfields_.DefaultModelFields.fields = def_fields

    def init_model(self):
        self._set_fields_name()
        return self.__class__

    def get_fields(self):
        return [self.__class__.__dict__[i] for i in self.__class__.__dict__ if not i.endswith('__')
                and not i.startswith('__') and i != 'model_display_field']

    def _set_fields_name(self):
        # default field
        for def_field in self._default_model_fields:
            for f in def_field:
                setattr(self.__class__, f, def_field[f])

        fieldsname = [i for i in self.__class__.__dict__ if not i.endswith('__') and not i.startswith('__')]
        for fieldname in fieldsname:
            if fieldname != 'model_display_field':
                self.__class__.__dict__[fieldname].set_fname(fieldname)


class MigrateModel:
    # simple table

    default_fields = [

    ]
    action: dbfields_.FieldAction = None
    name: str = ''
    fields: list[dbfields_._Field] = [

    ]

    def new_instance(self, name: str, fields: list[dbfields_._Field] = None):
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
        for dtab in cfg.DEFAULT_TABLES:
            if not dtab in self._query.show_tables():
                for query in cfg.DEFAULT_TABLES[dtab]:
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
                        .set_default_fields([dbfields_.IntField().set_fname('id').set_action(dbfields_.FieldAction.CREATE)])\
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
                            .set_default_fields([dbfields_.IntField().set_fname('id').sdbfields_.et_action(dbfields_.FieldAction.CREATE)]) \
                            .create()
                        applylog.append_table_in_log(app, filename)

            # запис в лог оновлення моделей якщо вони писутні.
            if mgr_models:
                _InsertMgrData().update_log()

        # якщо створених таблиць не знайдено, створити їх (перша міграція).
        if not self._query.select_from(cfg.DefLogTable.flow_tables.value, '*'):
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
                if not m_model.name in self._query.select_from(cfg.DefLogTable.flow_tables.value, 'tn'):
                    m_model.action = dbfields_.FieldAction.CREATE
            except Exception:
                raise ErrorValidation(f"Table creation validation error.")

        for tn in self._query.select_from(cfg.DefLogTable.flow_tables.value, 'tn'):
            if not tn in [i.name for i in self.migrate_models]:
                try:
                    # створення поля для позначення видалення і mgr_models == True
                    del_mgrmodel = MigrateModel().new_instance(tn)
                    uf = dbfields_.UndefinedField()
                    uf.action = dbfields_.UndefinedField().set_action(dbfields_.FieldAction.NOACTION)
                    del_mgrmodel.fields.append(uf)
                    self.migrate_models.append(del_mgrmodel)

                    table = self._query.select_from(cfg.DefLogTable.flow_tables.value, 'id, applystatus', f"tn = '{tn}'", list_format=False,
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
            for tn in self._query.select_from(cfg.DefLogTable.flow_tables.value, 'tn'):
                tn_ids[tn] = self._query.select_from(cfg.DefLogTable.flow_tables.value, 'id', f"tn = '{tn}'")[0]

            for tn in tn_ids:
                for i in self.migrate_models:
                    if i.name == tn:
                        table_fields = self._query.select_from(cfg.DefLogTable.flow_fields.value, 'fname', f"parent_table = '{tn_ids[tn]}'")
                        for tf in table_fields:
                            curfieldname = tf
                            if not tf in [j.fname for j in i.fields]:
                                i.fields.append(dbfields_.DelField().set_fname(tf))
        except Exception:
            raise ErrorValidation(f"Error validating deletion of field '{curfieldname}'.")

    def _create_fields_validation(self):
        curfieldname = ''
        try:
            tn_ids = {}
            for tn in self._query.select_from(cfg.DefLogTable.flow_tables.value, 'tn'):
                tn_ids[tn] = self._query.select_from(cfg.DefLogTable.flow_tables.value, 'id', f"tn = '{tn}'")[0]

            for model in self.migrate_models:
                for tn in tn_ids:
                    if model.name == tn:
                        for field in model.fields:
                            curfieldname = field.fname
                            flowfields = self._query.select_from(cfg.DefLogTable.flow_fields.value, 'fname, action', f"parent_table = '{tn_ids[tn]}'",
                                                             list_format=False, dictionary=True)
                            if not field.fname in [i['fname'] for i in flowfields]:
                                field.action = dbfields_.FieldAction.CREATE
                            else:
                                for dfield in flowfields:
                                    if field.fname == dfield['fname']:
                                        if dfield['action'] == dbfields_.FieldAction.DELETE.value:
                                            field.action = dbfields_.FieldAction.CREATE
                if not model.name in tn_ids:
                    for field in model.fields:
                        field.action = dbfields_.FieldAction.CREATE
        except Exception:
            raise ErrorValidation(f"Validation failed to create field '{curfieldname}'.")

    def _update_fields_validaton(self):
        tn_ids = {}
        for tn in self._query.select_from(cfg.DefLogTable.flow_tables.value, 'tn'):
            tn_ids[tn] = self._query.select_from(cfg.DefLogTable.flow_tables.value, 'id', f"tn = '{tn}'")[0]

        for model in self.migrate_models:
            for tn in tn_ids:
                if model.name == tn:
                    for field in model.fields:
                        try:
                            if field.fname in self._query.select_from(cfg.DefLogTable.flow_fields.value, 'fname', f"parent_table = '{tn_ids[tn]}'"):
                                field_data = self._query.custom_query(
                                    f"SELECT * FROM {cfg.DefLogTable.flow_fields.value} WHERE `parent_table` = '{tn_ids[tn]}' AND "
                                    f"`fname` = '{field.fname}'", dictionary=True)[0]
                                undef_field = dbfields_.UndefinedField()
                                for fd in field_data:
                                    exclude = list(dbfields_.DefaultModelFields.fields.keys()) + ['parent_table', 'applystatus', 'action']
                                    if not fd in exclude:
                                        if field_data[fd] == 'None':
                                            undef_field.__setattr__(fd, None)
                                        else:
                                            undef_field.__setattr__(fd, field_data[fd])

                                field_attr = [i for i in field.__dict__]
                                field_attr.remove('fname')
                                if field_values_to_dict(field) != field_values_to_dict(undef_field):
                                    field.action = dbfields_.FieldAction.UPDATE
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
                model.action = dbfields_.FieldAction.NOACTION
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
                    if not mgrmodel.name in self._query.select_from(cfg.DefLogTable.flow_tables.value, 'tn'):
                        tn.append(mgrmodel.name)
                        sngtn = mgrmodel.name
                        self._query.insert_data(cfg.DefLogTable.flow_tables.value, insert_values_to_str(
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
                        parent_table_id = self._query.select_from(cfg.DefLogTable.flow_tables.value, 'id', f"tn = '{mgrmodel.name}'")[0]
                        field_values_dict = field_values_to_dict(field)
                        field_values_dict['parent_table'] = parent_table_id
                        self._query.insert_data(cfg.DefLogTable.flow_fields.value, insert_values_to_str(**field_values_dict))
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
                        case dbfields_.FieldAction.CREATE:
                            try:
                                self._query.insert_data(cfg.DefLogTable.flow_tables.value, insert_values_to_str(tn=mgrmodel.name, action=dbfields_.FieldAction.CREATE.value))
                                self._insert_mgrmodel_fields_log(mgrmodel, mgrmodel.fields)
                            except Exception:
                                raise ErrorAddingTableToLog(tablename=mgrmodel.name)
                            finally:
                                print(_migration_log(f" - ✔️ The '{mgrmodel.name}' table has been added to the log."))
                        case dbfields_.FieldAction.NOACTION:
                            # оновлення даних про поля таблиць.
                            self._insert_mgrmodel_fields_log(mgrmodel, mgrmodel.fields)

    def _insert_mgrmodel_fields_log(self, mgrmodel: MigrateModel, fields: list[dbfields_._Field]):
        """
        Оновлення полів таблиць у логу.

        :param mgrmodel: Модель міграції.
        :param fields: Поля міграції
        """
        iscreated = False
        isupdated = False
        isdeleted = False
        for field in fields:
            match field.action:
                case dbfields_.FieldAction.CREATE:
                    try:
                        field_dict = self._get_field_dict(mgrmodel, field)
                        if field_dict:
                            field_dict = field_dict[0]
                            if field_dict and field_dict['action'] == dbfields_.FieldAction.DELETE.value:
                                self._change_field_action(field_dict['id'], dbfields_.FieldAction.CREATE)
                                iscreated = True
                        else:
                            self.flow_fields_insert(mgrmodel, field)
                            iscreated = True
                    except Exception:
                        raise ErrorAddingFieldToLog(fname=field.fname)
                    finally:
                        if iscreated:
                            print(_migration_log(f" -- ✔️ The '{field.fname}' field has been added to the log."))
                case dbfields_.FieldAction.UPDATE:
                    try:
                        field_dict = self._get_field_dict(mgrmodel, field)[0]
                        field_values = field_values_to_dict(field)
                        field_dict.update(field_values)

                        # якщо action = create нiчого не змiнюеться
                        if not field_dict['applystatus']:
                            field_dict['action'] = dbfields_.FieldAction.CREATE.value
                        else:
                            field_dict['action'] = dbfields_.FieldAction.UPDATE.value
                        self._query.update_data(cfg.DefLogTable.flow_fields.value, update_value_to_str(**field_dict),
                                                f"id = {field_dict['id']}")
                        isupdated = True
                    except Exception:
                        raise ErrorUpdateFieldInLog(fname=field.fname)
                    finally:
                        if isupdated:
                            print(_migration_log(f" -- ✔️ The field '{field.fname}' was successfully updated in the log."))
                case dbfields_.FieldAction.DELETE:
                    try:
                        field_dict = self._get_field_dict(mgrmodel, field)[0]
                        if field_dict['applystatus']:
                            self._change_field_action(field_dict['id'], dbfields_.FieldAction.DELETE)
                            isdeleted = True
                        else:
                            self._query.delete_field(cfg.DefLogTable.flow_fields.value, f"id={field_dict['id']}")
                            isdeleted = True
                    except Exception:
                        raise ErrorDeleteFieldInLog(field.fname)
                    finally:
                        if isdeleted:
                            print(_migration_log(f" -- ✔️ The field '{field.fname}' was successfully deleted in the log."))

    def _get_field_dict(self, mgrmodel: MigrateModel, field: dbfields_._Field) -> dict:
        """
        Перетворює дані MigrateModel у словник.
        """
        parent_table_id = self._query.select_from(cfg.DefLogTable.flow_tables.value, 'id',
                                                  f"tn = '{mgrmodel.name}'")[0]
        field_dict: dict = self._query.select_from(cfg.DefLogTable.flow_fields.value, '*',
                                                   f"`parent_table` = {parent_table_id} and "
                                                   f"fname = '{field.fname}'",
                                                   list_format=False, dictionary=True)
        return field_dict

    def _change_field_action(self, fid: int, action: dbfields_.FieldAction):
        self._query.update_data(cfg.DefLogTable.flow_fields.value, update_value_to_str(action=action.value), f"id={fid}")

    def flow_fields_insert(self, mgrmodel: MigrateModel, field: dbfields_._Field):
        """
        Створення нового поля у логу. Команда Create.
        """
        parent_table_id = self._query.select_from(cfg.DefLogTable.flow_tables.value, 'id', f"tn = '{mgrmodel.name}'")[0]
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
        self._query.insert_data(cfg.DefLogTable.flow_fields.value, insert_values_to_str(**insert_values))

    @staticmethod
    def delete_table(table: dict):
        # table: sql query dict
        from flow.database.query import DbQuery
        _query = DbQuery()

        if table['applystatus']:
            _query.update_data(cfg.DefLogTable.flow_tables.value, update_value_to_str(action=dbfields_.FieldAction.DELETE.value),
                                    f"`id` = {table['id']}")
        else:
            _query.delete_field(cfg.DefLogTable.flow_tables.value, f"`id` = {table['id']}")


class CreateMgrFramework:
    """
    Створеня файлу міграцій.
    """
    def __init__(self, model: Type[MigrateModel], filepath: str, filename: str, first_mgr: bool = False):
        from flow.database.query import DbQuery

        self.model = model
        if first_mgr:
            self.model.action = dbfields_.FieldAction.CREATE
        self.first_mgr = first_mgr
        self.filepath = filepath
        self.filename = filename
        self.default_fields: list[dbfields_._Field] = []
        self._query = DbQuery()

    def set_default_fields(self, fields: list[dbfields_._Field]):
        for field in fields:
            self.default_fields.append(field)
        return self

    def _get_default_fields(self):
        fields_str = ''
        for x, field in enumerate(self.default_fields):
            if x == 0:
                fields_str += f"fields.{field.get_strbuild()}.set_fname('{field.fname}').set_action(fields.{field.action}),\n"
            else:
                fields_str += f"        fields.{field.get_strbuild()}.set_fname('{field.fname}').set_action(fields.{field.action}),\n"
        return fields_str

    def _get_model_fields(self):
        fields_str = ''
        for x, field in enumerate(self.model.fields):
            if x == 0:
                if self.first_mgr:
                    fields_str += f"fields.{field.get_strbuild()}.set_fname('{field.fname}').set_action(fields.{dbfields_.FieldAction.CREATE}),\n"
                else:
                    fields_str += f"fields.{field.get_strbuild()}.set_fname('{field.fname}').set_action(fields.{field.action}),\n"
            else:
                if self.first_mgr:
                    fields_str += f"\t\tfields.{field.get_strbuild()}.set_fname('{field.fname}').set_action(fields.{dbfields_.FieldAction.CREATE}),\n"
                else:
                    fields_str += f"\t\tfields.{field.get_strbuild()}.set_fname('{field.fname}').set_action(fields.{field.action}),\n"
        return fields_str

    def _build_str_migrate_model(self, model_name, default_fields: str, model_fields: str, action: dbfields_.FieldAction) -> str:
        str_migrate_model = f"""\n
class Mgr{model_name}(models.MigrateModel):
    # simple table

    default_fields = [
        {default_fields}
    ]   
    action = fields.{action}
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
                    f.write("from flow.database.model import models, fields\n")

                f.write(self._build_str_migrate_model(self.model.name, self._get_default_fields(),
                                                      self._get_model_fields(), self.model.action))
        except Exception:
            raise ErrorWritingToFile(filepath=self.filepath)


class DbFMgrApplyLog:
    """
    Клас для керування таблицями логів.
    """
    def __init__(self):
        from flow.database.query import DbQuery

        self._query = DbQuery()

    def clear_table_data(self):
        self._query.clear_table(cfg.DefLogTable.appaply.value)

    def check_table_apply(self, filename: str) -> bool:
        """
        Перевірка наявності файла міграцій у логу.

        :param filename: Назва файла міграцій.
        """
        if not self._get_table_log():
            return False
        if filename.split('.')[0] in [i['filename'] for i in self._get_table_log()]:
            return True
        else:
            return False

    def append_table_in_log(self, appname: str, filename: str):
        """
        Добавлення поля у таблицю _appaply.
        """
        self._query.custom_query(f"INSERT INTO `{cfg.DefLogTable.appaply.value}` (`appname`, `filename`) VALUES ('{appname}', '{filename.split('.')[0]}')",
                                 dictionary=True)

    def _get_table_log(self) -> list:
        return self._query.custom_query(f'SELECT * FROM `{cfg.DefLogTable.appaply.value}`', dictionary=True)

    def change_applystatus(self, table_name: cfg.DefLogTable, applystatus: bool, action: dbfields_.FieldAction, fid: int):
        """
        Зміна статуса поля.

        :param table_name: Назва таблиці.
        :param applystatus: Новій статус.
        :param action: Нова дія для поля.
        :param fid: Id поля.
        """
        apply = ''
        if applystatus:
            apply = '1'
        else:
            apply = '0'
        self._query.update_data(table_name.value, update_value_to_str(applystatus=apply,
                                                        action=action.value), f"`id` = {fid}")

    def ffields_delete_field(self, field_id: int):
        self._query.delete_field(cfg.DefLogTable.flow_fields.value, f"`id` = {field_id}")

    def ftables_delete_field(self, field_id: int):
        self._query.delete_field(cfg.DefLogTable.flow_tables.value, f"`id` = {field_id}")


class TableLog:
    """
    Клас пердставляє нозву таблиці і всі її поля із логу.
    """
    def __init__(self, table: dict, fields: list[dict]):
        self._table = table
        self._fields = fields

    @property
    def table(self):
        return self._table

    @table.setter
    def table(self, table: dict):
        self._table = table

    @property
    def fields(self):
        return self._fields

    @fields.setter
    def fields(self, fields: list[dict]):
        self._table = fields


class ApplyMigrations:
    """
    Застосування всіх міграцій. Створення усіх таблиць і полів.
    """
    def __init__(self):
        from flow.database.query import DbQuery

        self._query = DbQuery()
        self.tables_log_list: list[TableLog] = self._get_models_log()
        self.dbapplylog = DbFMgrApplyLog()
        self._apply_fk_fields__create: list[dict] = []

    def _get_models_log(self) -> list:
        """
        Отримання даних із лога.
        """
        log = []
        tables = self._query.select_from(cfg.DefLogTable.flow_tables.value, '*', dictionary=True, list_format=False)
        fields = self._query.select_from(cfg.DefLogTable.flow_fields.value, '*', dictionary=True, list_format=False)
        for table in tables:
            tfields = []
            for field in fields:
                if field['parent_table'] == table['id']:
                    tfields.append(field)
            log.append(TableLog(table, tfields))
        return log

    def _filter(self, tables_log_list: list[TableLog]):
        """
        Поля і таблиці без змін не попадають у подальшу обробку.
        """
        fields = {}
        for table_log in tables_log_list:
            fields[table_log.table['tn']] = []
            for field in table_log.fields:
                if field['action'] == dbfields_.FieldAction.NOACTION.value:
                    fields[table_log.table['tn']].append(field)

            if not table_log.fields and table_log.table['action'] != 0:
                self.tables_log_list.remove(table_log)

        for table_log in tables_log_list:
            if table_log.table['tn'] in fields.keys():
                for f in fields[table_log.table['tn']]:
                    table_log.fields.remove(f)

    def apply(self):
        """
        Головний метод для застосування міграцій.
        У цьому методі виконується видалення, оновлення та створення нових таблиць та стовпців.

        :return:
        """
        self._filter(self.tables_log_list)

        for table_log in self.tables_log_list:
            match table_log.table['action']:
                # create table
                case dbfields_.FieldAction.CREATE.value:
                    tfields = []
                    for field in table_log.fields:
                        if field['parent_table'] == table_log.table['id']:
                            tfields.append(field)
                    self._create_table(table_log.table, tfields)
                # fields actions
                case dbfields_.FieldAction.NOACTION.value:
                    tfields = []
                    for field in table_log.fields:
                        if field['parent_table'] == table_log.table['id']:
                            tfields.append(field)
                    for f in tfields:
                        tn = table_log.table['tn']
                        match f['action']:
                            # create fields
                            case dbfields_.FieldAction.CREATE.value:
                                try:
                                    match f['ftype']:
                                        case dbfields_.FieldType.FK.value:
                                            cfield = f.copy()
                                            cfield['ftype'] = dbfields_.FieldType.INT.value
                                            self._query.create_column(tn, field_dict_to_sql(f))
                                            self.apply_fk(tn, cfield)
                                            self.dbapplylog.change_applystatus(cfg.DefLogTable.flow_fields, True, dbfields_.FieldAction.NOACTION,
                                                                            f['id'])
                                        case _:
                                            self._query.create_column(tn, field_dict_to_sql(f))
                                            self.dbapplylog.change_applystatus(cfg.DefLogTable.flow_fields, True, dbfields_.FieldAction.NOACTION,
                                                                               f['id'])
                                except Exception as e:
                                    raise e
                                finally:
                                    print(_migration_log(f" -- ✔ The field {f['fname']} was created in the table {tn}."))
                            # delete fields
                            case dbfields_.FieldAction.DELETE.value:
                                try:
                                    fk_name = self._query.show_fk_relation_name(f['fname'])
                                    if fk_name:
                                        self._query.delete_relation(tn, fk_name[0])
                                    self._query.delete_column(tn, f['fname'])
                                    self.dbapplylog.ffields_delete_field(f['id'])
                                except Exception as e:
                                    raise e
                                finally:
                                    print(_migration_log(f" -- ✔ The field {f['fname']} was deleted in the table {tn}."))
                            # update fields
                            case dbfields_.FieldAction.UPDATE.value:
                                try:
                                    match f['ftype']:
                                        case dbfields_.FieldType.FK.value:
                                            ufield = f.copy()
                                            ufield['ftype'] = dbfields_.FieldType.INT.value
                                            self._query.update_table_attr(tn, ufield['fname'], field_dict_to_sql(ufield))
                                            if not self._query.show_fk_relation_name(f['fname']):
                                                self.apply_fk(tn, ufield)
                                            self.dbapplylog.change_applystatus(cfg.DefLogTable.flow_fields, True,
                                                                            dbfields_.FieldAction.NOACTION, f['id'])
                                        case _:
                                            fk_name = self._query.show_fk_relation_name(f['fname'])
                                            if fk_name:
                                                self._query.delete_relation(tn, fk_name[0])
                                                self._query.update_table_attr(tn, f['fname'], field_dict_to_sql(f))
                                                self.dbapplylog.change_applystatus(cfg.DefLogTable.flow_fields, True,
                                                                                dbfields_.FieldAction.NOACTION, f['id'])
                                            else:
                                                self._query.update_table_attr(tn, f['fname'], field_dict_to_sql(f))
                                                self.dbapplylog.change_applystatus(cfg.DefLogTable.flow_fields, True,
                                                                                dbfields_.FieldAction.NOACTION, f['id'])
                                except Exception as e:
                                    raise e
                                finally:
                                    print(_migration_log(f" -- ✔ The field {f['fname']} was updated in the table {tn}."))
                # delete tables
                case dbfields_.FieldAction.DELETE.value:
                    try:
                        self._query.delele_table(table_log.table['tn'])
                        self.dbapplylog.ftables_delete_field(table_log.table['id'])
                    except Exception as e:
                        raise e
                    finally:
                        print(_migration_log(f" - ✔ The table {table_log.table['tn']} deleted."))

        # добавлення зв'язка fk у раніше визначених полях (_create_table)
        for fkc in self._apply_fk_fields__create:
            for tn in fkc:
                self.apply_fk(tn, fkc[tn])

    def _create_table(self, table: dict, fields: list[dict]):
        """
        Створення нової таблиці і полів да неї.
        """

        strfields = '( '
        for x, f in enumerate(fields):
            if x == len(fields)-1:
                strfields += field_dict_to_sql(f) + ' )'
            else:
                strfields += field_dict_to_sql(f) + ', '

        try:
            # create table and dfields
            self._query.create_table(table['tn'], strfields)
            self.dbapplylog.change_applystatus(cfg.DefLogTable.flow_tables, True, dbfields_.FieldAction.NOACTION, table['id'])
        except Exception:
            raise CreationError(msg=f"Error creating table {table['tn']}")
        finally:
            print(_migration_log(f" - ✔ {table['tn']} table created."))
            # зміна статуса кожного стовпця у логу та застосування різниих додаткових методів.
            for field in fields:
                try:
                    match field['ftype']:
                        case dbfields_.FieldType.FK.value:
                            # apply fk field
                            self._apply_fk_fields__create.append({table['tn']: field})
                            self.dbapplylog.change_applystatus(cfg.DefLogTable.flow_fields, True, dbfields_.FieldAction.NOACTION, field['id'])
                        case dbfields_.FieldType.AUTOINCREMENT.value:
                            self.apply_auto_field(table['tn'], field)
                            self.dbapplylog.change_applystatus(cfg.DefLogTable.flow_fields, True, dbfields_.FieldAction.NOACTION, field['id'])
                        case _:
                            self.dbapplylog.change_applystatus(cfg.DefLogTable.flow_fields, True, dbfields_.FieldAction.NOACTION, field['id'])
                except Exception:
                    raise CreationError(msg=f"Error creating field {field['fname']} in table {table['tn']}")
                finally:
                    print(_migration_log(f" -- ✔ The field {field['fname']} was created in the table {table['tn']}."))

    def apply_auto_field(self, table_name: str, field_log: dict):
        fstr = field_dict_to_sql(field_log)
        fstr += f"AUTO_INCREMENT, add PRIMARY KEY (`{field_log['fname']}`)"
        self._query.update_table_attr(table_name, field_log['fname'], fstr)

    def apply_fk(self, table_name, field_log: dict):
        self._query.add_fk(table_name, field_log['fname'], field_log['fk'].lower(), 'id', field_log['on_delete'], field_log['on_update'])


def field_dict_to_sql(field_dict: dict) -> str:
    """
    Перетворяння словника на sql у форматі рядка.

    :return:
    """
    field_dict = field_dict.copy()
    fstr = ''
    match field_dict['ftype']:
        case dbfields_.FieldType.FK.value:
            field_dict['ftype'] = dbfields_.FieldType.INT.value
        case dbfields_.FieldType.AUTOINCREMENT.value:
            field_dict['ftype'] = dbfields_.FieldType.INT.value

    if not field_dict['flength']:
        field_dict['flength'] = ''
    if field_dict['fnull']:
        field_dict['fnull'] = 'NULL'
    else:
        field_dict['fnull'] = 'NOT NULL'
    for attr in field_dict:
        if not attr in ['id', 'parent_table', 'flength', 'fk', 'applystatus', 'action', 'on_delete', 'on_update', 'rel_name']:
            match attr:
                case 'fname':
                    fstr += f"`{field_dict[attr]}` "
                case 'ftype':
                    if field_dict['flength']:
                        fstr += f"{field_dict[attr]}({field_dict['flength']}) "
                    else:
                        fstr += f"{field_dict[attr]} "
                case _:
                    if field_dict[attr] != 'None':
                        fstr += f"{field_dict[attr]} "
    return fstr


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


def field_values_to_dict(field: dbfields_._Field) -> dict:
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
