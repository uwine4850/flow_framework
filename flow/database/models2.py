from enum import Enum
import importlib
from fconfig.fsettings import APPS
from flow.config.conf import DefLogTable, DEFAULT_TABLES
import os
import datetime
from typing import Type
from flow.exceptions.migrate_exceptions import ErrorWritingToFile, ErrorAddingTableToLog, ErrorAddingFieldToLog,\
    ErrorUpdateFieldInLog, ErrorDeleteFieldInLog, ErrorDeleteTableInLog, ErrorValidation, CreationError, ApplyValidationError


class FieldType(Enum):
    INT = 'INT'
    FK = 'FK'
    CHAR = 'VARCHAR'
    AUTOINCREMENT = 'AUTOI'


class FieldAction(Enum):
    DELETE = 'DELETE'
    UPDATE = 'UPDATE'
    CREATE = 'CREATE'
    NOACTION = 'NOACTION'


class RelationAction(Enum):
    CASCADE = 'CASCADE'
    RESTRICT = 'RESTRICT'
    SETNULL = 'SETNULL'
    NOACTION = 'NOACTION'


# розділити на 2
class _Field:
    def __init__(self):
        self.fname: str = ''
        self.ftype: FieldType = None
        self.flength: int = 0
        self.fk: str = None
        self.on_delete: RelationAction = None
        self.on_update: RelationAction = None
        self.rel_name = None
        self.fnull: bool = False
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


class AutoIncrementField(_Field):
    def __init__(self):
        super().__init__()
        self.ftype = FieldType.AUTOINCREMENT

    def get_strbuild(self) -> str:
        return f'AutoIncrementField()'


class ForeignKey(_Field):
    def __init__(self, fk: str, on_delete: RelationAction, on_update: RelationAction = RelationAction.RESTRICT, rel_name='', fnull: bool = False):
        super().__init__()
        self.on_delete = on_delete
        self.on_update = on_update
        self.ftype = FieldType.FK
        self.fk = fk
        self.fnull = fnull
        if rel_name:
            self.rel_name = rel_name

    def get_strbuild(self) -> str:
        if self.fk:
            return f"ForeignKey(fk='{self.fk}', fnull={self.fnull}, " \
                   f"on_delete=models2.{self.on_delete}, on_update=models2.{self.on_update}, rel_name='{self.rel_name}')"
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


class CharField(_Field):
    def __init__(self, flength: int, fnull: bool = False):
        super().__init__()
        self.ftype = FieldType.CHAR
        self.flength = flength
        self.fnull = fnull

    def get_strbuild(self) -> str:
        return f'CharField(flength={self.flength}, fnull={self.fnull})'


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


class DefaultModelFields:
    fields = {
        'id': AutoIncrementField()
    }


class Model:
    _default_model_fields = [DefaultModelFields.fields]

    def set_default_fields(self, def_fields: list):
        self._default_model_fields = def_fields
        DefaultModelFields.fields = def_fields

    def init_model(self):
        self._set_fields_name()
        return self.__class__

    def get_fields(self):
        return [self.__class__.__dict__[i] for i in self.__class__.__dict__ if not i.endswith('__')
                and not i.startswith('__')]

    def _set_fields_name(self):
        # default field
        for def_field in self._default_model_fields:
            for f in def_field:
                setattr(self.__class__, f, def_field[f])

        fieldsname = [i for i in self.__class__.__dict__ if not i.endswith('__') and not i.startswith('__')]
        for fieldname in fieldsname:
            self.__class__.__dict__[fieldname].set_fname(fieldname)


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
        if not self._query.select_from(DefLogTable.flow_tables.value, '*'):
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
                if not m_model.name in self._query.select_from(DefLogTable.flow_tables.value, 'tn'):
                    m_model.action = FieldAction.CREATE
            except Exception:
                raise ErrorValidation(f"Table creation validation error.")

        for tn in self._query.select_from(DefLogTable.flow_tables.value, 'tn'):
            if not tn in [i.name for i in self.migrate_models]:
                try:
                    # створення поля для позначення видалення і mgr_models == True
                    del_mgrmodel = MigrateModel().new_instance(tn)
                    uf = _UndefinedField()
                    uf.action = _UndefinedField().set_action(FieldAction.NOACTION)
                    del_mgrmodel.fields.append(uf)
                    self.migrate_models.append(del_mgrmodel)

                    table = self._query.select_from(DefLogTable.flow_tables.value, 'id, applystatus', f"tn = '{tn}'", list_format=False,
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
            for tn in self._query.select_from(DefLogTable.flow_tables.value, 'tn'):
                tn_ids[tn] = self._query.select_from(DefLogTable.flow_tables.value, 'id', f"tn = '{tn}'")[0]

            for tn in tn_ids:
                for i in self.migrate_models:
                    if i.name == tn:
                        table_fields = self._query.select_from(DefLogTable.flow_fields.value, 'fname', f"parent_table = '{tn_ids[tn]}'")
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
            for tn in self._query.select_from(DefLogTable.flow_tables.value, 'tn'):
                tn_ids[tn] = self._query.select_from(DefLogTable.flow_tables.value, 'id', f"tn = '{tn}'")[0]

            for model in self.migrate_models:
                for tn in tn_ids:
                    if model.name == tn:
                        for field in model.fields:
                            curfieldname = field.fname
                            flowfields = self._query.select_from(DefLogTable.flow_fields.value, 'fname, action', f"parent_table = '{tn_ids[tn]}'",
                                                             list_format=False, dictionary=True)
                            if not field.fname in [i['fname'] for i in flowfields]:
                                field.action = FieldAction.CREATE
                            else:
                                for dfield in flowfields:
                                    if field.fname == dfield['fname']:
                                        if dfield['action'] == FieldAction.DELETE.value:
                                            field.action = FieldAction.CREATE
                if not model.name in tn_ids:
                    for field in model.fields:
                        field.action = FieldAction.CREATE
        except Exception:
            raise ErrorValidation(f"Validation failed to create field '{curfieldname}'.")

    def _update_fields_validaton(self):
        tn_ids = {}
        for tn in self._query.select_from(DefLogTable.flow_tables.value, 'tn'):
            tn_ids[tn] = self._query.select_from(DefLogTable.flow_tables.value, 'id', f"tn = '{tn}'")[0]

        for model in self.migrate_models:
            for tn in tn_ids:
                if model.name == tn:
                    for field in model.fields:
                        try:
                            if field.fname in self._query.select_from(DefLogTable.flow_fields.value, 'fname', f"parent_table = '{tn_ids[tn]}'"):
                                field_data = self._query.custom_query(
                                    f"SELECT * FROM {DefLogTable.flow_fields.value} WHERE `parent_table` = '{tn_ids[tn]}' AND "
                                    f"`fname` = '{field.fname}'", dictionary=True)[0]
                                undef_field = _UndefinedField()
                                for fd in field_data:
                                    exclude = list(DefaultModelFields.fields.keys()) + ['parent_table', 'applystatus', 'action']
                                    if not fd in exclude:
                                        if field_data[fd] == 'None':
                                            undef_field.__setattr__(fd, None)
                                        else:
                                            undef_field.__setattr__(fd, field_data[fd])

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
                    if not mgrmodel.name in self._query.select_from(DefLogTable.flow_tables.value, 'tn'):
                        tn.append(mgrmodel.name)
                        sngtn = mgrmodel.name
                        self._query.insert_data(DefLogTable.flow_tables.value, insert_values_to_str(
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
                        parent_table_id = self._query.select_from(DefLogTable.flow_tables.value, 'id', f"tn = '{mgrmodel.name}'")[0]
                        field_values_dict = field_values_to_dict(field)
                        field_values_dict['parent_table'] = parent_table_id
                        self._query.insert_data(DefLogTable.flow_fields.value, insert_values_to_str(**field_values_dict))
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
                                self._query.insert_data(DefLogTable.flow_tables.value, insert_values_to_str(tn=mgrmodel.name, action=FieldAction.CREATE.value))
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
        iscreated = False
        isupdated = False
        isdeleted = False
        for field in fields:
            match field.action:
                case FieldAction.CREATE:
                    try:
                        field_dict = self._get_field_dict(mgrmodel, field)
                        if field_dict:
                            field_dict = field_dict[0]
                            if field_dict and field_dict['action'] == FieldAction.DELETE.value:
                                self._change_field_action(field_dict['id'], FieldAction.CREATE)
                                iscreated = True
                        else:
                            self.flow_fields_insert(mgrmodel, field)
                            iscreated = True
                    except Exception:
                        raise ErrorAddingFieldToLog(fname=field.fname)
                    finally:
                        if iscreated:
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
                        self._query.update_data(DefLogTable.flow_fields.value, update_value_to_str(**field_dict),
                                                f"id = {field_dict['id']}")
                        isupdated = True
                    except Exception:
                        raise ErrorUpdateFieldInLog(fname=field.fname)
                    finally:
                        if isupdated:
                            print(_migration_log(f" -- ✔️ The field '{field.fname}' was successfully updated in the log."))
                case FieldAction.DELETE:
                    try:
                        field_dict = self._get_field_dict(mgrmodel, field)[0]
                        if field_dict['applystatus']:
                            self._change_field_action(field_dict['id'], FieldAction.DELETE)
                            isdeleted = True
                        else:
                            self._query.delete_field(DefLogTable.flow_fields.value, f"id={field_dict['id']}")
                            isdeleted = True
                    except Exception:
                        raise ErrorDeleteFieldInLog(field.fname)
                    finally:
                        if isdeleted:
                            print(_migration_log(f" -- ✔️ The field '{field.fname}' was successfully deleted in the log."))

    def _get_field_dict(self, mgrmodel: MigrateModel, field: _Field) -> dict:
        """
        Перетворює дані MigrateModel у словник.
        """
        parent_table_id = self._query.select_from(DefLogTable.flow_tables.value, 'id',
                                                  f"tn = '{mgrmodel.name}'")[0]
        field_dict: dict = self._query.select_from(DefLogTable.flow_fields.value, '*',
                                                   f"`parent_table` = {parent_table_id} and "
                                                   f"fname = '{field.fname}'",
                                                   list_format=False, dictionary=True)
        return field_dict

    def _change_field_action(self, fid: int, action: FieldAction):
        self._query.update_data(DefLogTable.flow_fields.value, update_value_to_str(action=action.value), f"id={fid}")

    def flow_fields_insert(self, mgrmodel: MigrateModel, field: _Field):
        """
        Створення нового поля у логу. Команда Create.
        """
        parent_table_id = self._query.select_from(DefLogTable.flow_tables.value, 'id', f"tn = '{mgrmodel.name}'")[0]
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
        self._query.insert_data(DefLogTable.flow_fields.value, insert_values_to_str(**insert_values))

    @staticmethod
    def delete_table(table: dict):
        # table: sql query dict
        from flow.database.query import DbQuery
        _query = DbQuery()

        if table['applystatus']:
            _query.update_data(DefLogTable.flow_tables.value, update_value_to_str(action=FieldAction.DELETE.value),
                                    f"`id` = {table['id']}")
        else:
            _query.delete_field(DefLogTable.flow_tables.value, f"`id` = {table['id']}")


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
    """
    Клас для керування таблицями логів.
    """
    def __init__(self):
        from flow.database.query import DbQuery

        self._query = DbQuery()

    def clear_table_data(self):
        self._query.clear_table(DefLogTable.appaply.value)

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
        self._query.custom_query(f"INSERT INTO `{DefLogTable.appaply.value}` (`appname`, `filename`) VALUES ('{appname}', '{filename.split('.')[0]}')",
                                 dictionary=True)

    def _get_table_log(self) -> list:
        return self._query.custom_query(f'SELECT * FROM `{DefLogTable.appaply.value}`', dictionary=True)

    def change_applystatus(self, table_name: DefLogTable, applystatus: bool, action: FieldAction, fid: int):
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
        self._query.delete_field(DefLogTable.flow_fields.value, f"`id` = {field_id}")

    def ftables_delete_field(self, field_id: int):
        self._query.delete_field(DefLogTable.flow_tables.value, f"`id` = {field_id}")


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
        tables = self._query.select_from(DefLogTable.flow_tables.value, '*', dictionary=True, list_format=False)
        fields = self._query.select_from(DefLogTable.flow_fields.value, '*', dictionary=True, list_format=False)
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
                if field['action'] == FieldAction.NOACTION.value:
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
                case FieldAction.CREATE.value:
                    tfields = []
                    for field in table_log.fields:
                        if field['parent_table'] == table_log.table['id']:
                            tfields.append(field)
                    self._create_table(table_log.table, tfields)
                # fields actions
                case FieldAction.NOACTION.value:
                    tfields = []
                    for field in table_log.fields:
                        if field['parent_table'] == table_log.table['id']:
                            tfields.append(field)
                    for f in tfields:
                        tn = table_log.table['tn']
                        match f['action']:
                            # create fields
                            case FieldAction.CREATE.value:
                                try:
                                    match f['ftype']:
                                        case FieldType.FK.value:
                                            cfield = f.copy()
                                            cfield['ftype'] = FieldType.INT.value
                                            self._query.create_column(tn, field_dict_to_sql(f))
                                            self.apply_fk(tn, cfield)
                                            self.dbapplylog.change_applystatus(DefLogTable.flow_fields, True, FieldAction.NOACTION,
                                                                            f['id'])
                                        case _:
                                            self._query.create_column(tn, field_dict_to_sql(f))
                                            self.dbapplylog.change_applystatus(DefLogTable.flow_fields, True, FieldAction.NOACTION,
                                                                               f['id'])
                                except Exception as e:
                                    raise e
                                finally:
                                    print(_migration_log(f" -- ✔ The field {f['fname']} was created in the table {tn}."))
                            # delete fields
                            case FieldAction.DELETE.value:
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
                            case FieldAction.UPDATE.value:
                                try:
                                    match f['ftype']:
                                        case FieldType.FK.value:
                                            ufield = f.copy()
                                            ufield['ftype'] = FieldType.INT.value
                                            self._query.update_table_attr(tn, ufield['fname'], field_dict_to_sql(ufield))
                                            if not self._query.show_fk_relation_name(f['fname']):
                                                self.apply_fk(tn, ufield)
                                            self.dbapplylog.change_applystatus(DefLogTable.flow_fields, True,
                                                                            FieldAction.NOACTION, f['id'])
                                        case _:
                                            fk_name = self._query.show_fk_relation_name(f['fname'])
                                            if fk_name:
                                                self._query.delete_relation(tn, fk_name[0])
                                                self._query.update_table_attr(tn, f['fname'], field_dict_to_sql(f))
                                                self.dbapplylog.change_applystatus(DefLogTable.flow_fields, True,
                                                                                FieldAction.NOACTION, f['id'])
                                            else:
                                                self._query.update_table_attr(tn, f['fname'], field_dict_to_sql(f))
                                                self.dbapplylog.change_applystatus(DefLogTable.flow_fields, True,
                                                                                FieldAction.NOACTION, f['id'])
                                except Exception as e:
                                    raise e
                                finally:
                                    print(_migration_log(f" -- ✔ The field {f['fname']} was updated in the table {tn}."))
                # delete tables
                case FieldAction.DELETE.value:
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
            self.dbapplylog.change_applystatus(DefLogTable.flow_tables, True, FieldAction.NOACTION, table['id'])
        except Exception:
            raise CreationError(msg=f"Error creating table {table['tn']}")
        finally:
            print(_migration_log(f" - ✔ {table['tn']} table created."))
            # зміна статуса кожного стовпця у логу та застосування різниих додаткових методів.
            for field in fields:
                try:
                    match field['ftype']:
                        case FieldType.FK.value:
                            # apply fk field
                            self._apply_fk_fields__create.append({table['tn']: field})
                            self.dbapplylog.change_applystatus(DefLogTable.flow_fields, True, FieldAction.NOACTION, field['id'])
                        case FieldType.AUTOINCREMENT.value:
                            self.apply_auto_field(table['tn'], field)
                            self.dbapplylog.change_applystatus(DefLogTable.flow_fields, True, FieldAction.NOACTION, field['id'])
                        case _:
                            self.dbapplylog.change_applystatus(DefLogTable.flow_fields, True, FieldAction.NOACTION, field['id'])
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
        case FieldType.FK.value:
            field_dict['ftype'] = FieldType.INT.value
        case FieldType.AUTOINCREMENT.value:
            field_dict['ftype'] = FieldType.INT.value

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
