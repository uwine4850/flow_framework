from enum import Enum
import importlib
from fconfig.fsettings import APPS
import os
import datetime
from typing import Type


class FieldType(Enum):
    INT = 'INT'


class FieldAction(Enum):
    DELETE = 'DELETE'
    UPDATE = 'UPDATE'
    CREATE = 'CREATE'
    NOACTION = 'NOACTION'


class Model:
    def get_model(self):
        self._set_fields_name()
        return self.__class__

    def _set_fields_name(self):
        fieldsname = [i for i in self.__class__.__dict__ if not i.endswith('__') and not i.startswith('__')]
        for fieldname in fieldsname:
            self.__class__.__dict__[fieldname].set_fname(fieldname)


class _Field:
    fname: str = ''
    ftype: FieldType
    flength: int = None
    fnull: bool = None
    action: FieldAction = None

    def get_strbuild(self) -> str:
        pass

    def set_action(self, action: FieldAction):
        self.action = action
        return self

    def set_fname(self, fname: str):
        self.fname = fname
        return self


class IntField(_Field):
    def __init__(self, flength: int = None, fnull: bool = False):
        self.ftype = FieldType.INT
        self.flength = flength
        self.fnull = fnull

    def get_strbuild(self) -> str:
        if self.flength:
            return f'IntField(flength={self.flength}, fnull={self.fnull})'
        else:
            return f'IntField(fnull={self.fnull})'


class MigrateModel:
    # simple table

    default_fields = [

    ]
    name: str = ''
    fields: list[_Field] = [

    ]

    def new_instance(self, name: str, fields: list[_Field]):
        self.name = name
        self.fields = fields
        return self


class Migrate:
    def __init__(self, models_dict: dict[str, list[Type[Model]]]):
        self.models_dict = models_dict
        self._migrate_apps()

    def _migrate_apps(self):
        mgr_files: dict[str] = {}
        remove_mgr = []

        for key in self.models_dict:
            for model in self.models_dict[key]:
                path = self._get_mgr_path(model().get_model())
                if not os.path.exists(path):
                    os.mkdir(path)

                if os.path.exists(path):
                    mgr_files[key] = path

        for key in mgr_files:
            filename = f"mgr_{datetime.datetime.now().strftime('%y_%m_%d__%H_%M_%S')}.py"
            filepath = os.path.join(mgr_files[key], filename)
            path, dirs, files = next(os.walk(mgr_files[key]))
            applylog = DbTableApplyLog()

            if not files:
                for model in self.models_dict[key]:
                    CreateMgrFramework(model=model().get_model(), filepath=filepath, filename=filename, first_mgr=True) \
                                        .set_default_fields([IntField().set_fname('id').set_action(FieldAction.CREATE)])\
                                        .create()
                applylog.append_table_in_log(key, filename, apply_value=False)
            else:
                old_file = _sorted_folder_items(files)[0]
                if applylog.check_table_apply(key, old_file):
                    imp_str = os.path.join(mgr_files[key], old_file).split('.')[0].replace('/', '.')
                    importlib.import_module(imp_str)

                    old_models = MigrateModel.__subclasses__()
                    for r in remove_mgr:
                        old_models.remove(r)
                    #for x, model in enumerate(old_models):
                        #_TableValidation(model, self.models_dict).validate()
                        #_MigrateValidation(model, self.models_dict[key][x], filepath, filename).validate()
                    #    remove_mgr.append(model)
                    not_del_old_models = []
                    del_table = False
                    for model in old_models:
                        if not model.name in [i.name for i in _TableValidation(model, self.models_dict).validate()]:
                            not_del_old_models.append(model)
                        else:
                            del_table = True
                        remove_mgr.append(model)
                    #for x, model in enumerate(not_del_old_models):
                    #    _MigrateValidation(model, self.models_dict[key][x], filepath, filename, del_table).validate()

                    applylog.append_table_in_log(key, filename, apply_value=False)
                else:
                    print(f"Migrations file '{old_file}' to application '{key}' has not been applied to the database.")

    def _get_mgr_path(self, model: Type[Model]) -> str:
        return f"{model.__module__.split('.')[0]}/migrations"


class ItemValidaton:
    def __init__(self, old_model: Type[MigrateModel], new_models: dict[str, list[Type[Model]]]):
        self.old_model = old_model
        self.new_migrate_models: dict[str, list[Type[MigrateModel]]] = {}
        self._crete_new_migrate_models(new_models)

    def _crete_new_migrate_models(self, new_models: dict[str, list[Type[Model]]]):
        for appname in new_models:
            for model in new_models[appname]:
                fields = [getattr(model, i) for i in model.__dict__
                                               if not i.endswith('__') and not i.startswith('__')]
                if appname in self.new_migrate_models:
                    self.new_migrate_models[appname].append(MigrateModel().new_instance(model.__name__, fields))
                else:
                    self.new_migrate_models[appname] = []
                    self.new_migrate_models[appname].append(MigrateModel().new_instance(model.__name__, fields))

    def validate(self):
        raise NotImplementedError


class _TableValidation(ItemValidaton):
    def __init__(self, old_model: Type[MigrateModel], new_models: dict[str, list[Type[Model]]]):
        from flow.database.query import DbQuery

        self._query = DbQuery()
        super().__init__(old_model, new_models)

    def validate(self) -> list[Type[MigrateModel]]:
        new_model_names = []
        del_tables = []
        for appname in self.new_migrate_models:
            for model in self.new_migrate_models[appname]:
                new_model_names.append(model.name.lower())
        if not self.old_model.name in new_model_names:
            self._query.delele_table(self.old_model.name)
            print(f"del table {self.old_model.name}")
            del_tables.append(self.old_model)
        return del_tables


class CreateMgrFramework:
    def __init__(self, model: Type[Model], filepath: str, filename: str, first_mgr: bool = False):
        from flow.database.query import DbQuery

        self.model = model
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
                fields_str += f"models.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models.{field.action}),\n"
            else:
                fields_str += f"        models.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models.{field.action}),\n"
        return fields_str

    def _get_model_fields(self):
        fields_str = ''
        fieldsname = [i for i in self.model.__dict__ if not i.endswith('__') and not i.startswith('__')]
        for x, fieldname in enumerate(fieldsname):
            field: _Field = getattr(self.model, fieldname)
            if x == 0:
                if self.first_mgr:
                    fields_str += f"models.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models.{FieldAction.CREATE}),\n"
                else:
                    fields_str += f"models.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models.{field.action}),\n"
            else:
                if self.first_mgr:
                    fields_str += f"\t\tmodels.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models.{FieldAction.CREATE}),\n"
                else:
                    fields_str += f"\t\tmodels.{field.get_strbuild()}.set_fname('{field.fname}').set_action(models.{field.action}),\n"
        return fields_str

    def _build_str_migrate_model(self, model_name, default_fields: str, model_fields: str) -> str:
        str_migrate_model = f"""\n
class Mgr{model_name}(models.MigrateModel):
    # simple table
    
    default_fields = [
        {default_fields}
    ]
    name = '{model_name}'
    fields = [
        {model_fields}
    ]
    """
        return str_migrate_model

    def create(self):
        with open(self.filepath, 'a') as f:
            # перевірка файла на пустоту
            if os.stat(self.filepath).st_size == 0:
                f.write("from flow.database import models\n")

            f.write(self._build_str_migrate_model(self.model.__name__.lower(), self._get_default_fields(), self._get_model_fields()))


class _MigrateValidation:
    def __init__(self, old_model: Type[MigrateModel], new_model: Model, filepath: str, filename: str, del_table: bool):
        self.model_for_create_mgr = new_model
        self.old_model = old_model
        model_fields = [getattr(new_model, i) for i in new_model.__dict__
                        if not i.endswith('__') and not i.startswith('__')]
        self.new_model = MigrateModel().new_instance(new_model.__name__, model_fields)
        self.filepath = filepath
        self.filename = filename
        self.del_table = del_table

    def validate(self):
        self._reset_old_model()
        self._del_validation()
        self._create_validation()
        self._update_validation()
        migrate = False
        for field in self.new_model.fields:
            if field.action != FieldAction.NOACTION:
                migrate = True

        if self.del_table:
            migrate = True

        if migrate:
            self._create_mgr()
        else:
            print(f'{self.new_model.name}: No changes found.')

    def _del_validation(self):
        for field in self.old_model.fields:
            if not field.fname in [i.fname for i in self.new_model.fields if not i.action]:
                delfield = field
                delfield.action = FieldAction.DELETE
                setattr(self.model_for_create_mgr, delfield.fname, delfield)

    def _create_validation(self):
        for field in self.new_model.fields:
            if not field.fname in [i.fname for i in self.old_model.fields]:
                field.action = FieldAction.CREATE

    def _update_validation(self):
        update_felds = []

        for new_field in self.new_model.fields:
            for old_field in self.old_model.fields:
                if not new_field.action and new_field.fname == old_field.fname:
                    for i in new_field.__dict__:
                        if i != 'action':
                            if getattr(new_field, i) != getattr(old_field, i):
                                update_felds.append(new_field.fname)

        for upd in update_felds:
            for f in self.new_model.fields:
                if f.fname == upd:
                    f.action = FieldAction.UPDATE

        for nfield in self.new_model.fields:
            if not nfield.action:
                nfield.action = FieldAction.NOACTION

    def _create_mgr(self):
        CreateMgrFramework(model=self.model_for_create_mgr, filepath=self.filepath, filename=self.filename) \
                    .set_default_fields([IntField().set_fname('id').set_action(FieldAction.NOACTION)])\
                    .create()

    def _reset_old_model(self):
        del_fields = []
        for x, field in enumerate(self.old_model.fields):
            if field.action == FieldAction.DELETE:
                del_fields.append(field)
            else:
                field.action = FieldAction.NOACTION

        for i in del_fields:
            self.old_model.fields.remove(i)


class ApplyMigrations:
    def __init__(self):
        from flow.database.query import DbQuery

        self.migrations_dict: dict[str, list[MigrateModel]] = {}
        self._query = DbQuery()
        self._get_migrations()
        self.applylog = DbTableApplyLog()
        if self.migrations_dict:
            self.apply()
        else:
            print('No new migrations found.')

    def _get_migrations(self):
        appended_mgrmodel = []
        for app in APPS:
            path, dirs, files = next(os.walk(f'{app}/migrations'))
            sorted_files = _sorted_folder_items(files)
            importlib.import_module(f'{app}.migrations.{sorted_files[0].split(".")[0]}')
            if not DbTableApplyLog().check_table_apply(app, sorted_files[0]):
                if app + sorted_files[0].split(".")[0] in self.migrations_dict.keys():
                    mgrlist = list(set(MigrateModel.__subclasses__())-set(appended_mgrmodel))

                    for mgrmodel in mgrlist:
                        self.migrations_dict[app + sorted_files[0].split(".")[0]].append(mgrmodel)
                        appended_mgrmodel.append(mgrmodel)
                else:
                    mgrlist = list(set(MigrateModel.__subclasses__())-set(appended_mgrmodel))

                    self.migrations_dict[app + sorted_files[0].split(".")[0]] = []
                    for mgrmodel in mgrlist:
                        self.migrations_dict[app + sorted_files[0].split(".")[0]].append(mgrmodel)
                        appended_mgrmodel.append(mgrmodel)

    def _create_tables(self):
        for app in self.migrations_dict:
            for mgr in self.migrations_dict[app]:
                if not mgr.name in self._query.show_tables():
                    self._query.create_table(mgr.name.lower(), mgr.default_fields)

    def _apply_actions(self):
        for app in self.migrations_dict:
            for mgr in self.migrations_dict[app]:
                if mgr.name in self._query.show_tables():
                    for field in mgr.fields:
                        match field.action:
                            case FieldAction.CREATE:
                                self._query.create_field(mgr.name, field)
                            case FieldAction.DELETE:
                                self._query.delete_field(mgr.name, field)
                            case FieldAction.UPDATE:
                                self._query.update_field(mgr.name, field)
                            case _:
                                pass
            self.applylog.change_apply_status(app, True)

    def delete_tables(self):
        table_names = []
        for i in self.migrations_dict.keys():
            for table in self.migrations_dict[i]:
                table_names.append(table.name)
        print(table_names, self._query.show_tables())

    def apply(self):
        self.delete_tables()
        self._create_tables()
        self._apply_actions()


class DbTableApplyLog:
    def __init__(self):
        from flow.database.query import DbQuery

        self._query = DbQuery()

    def check_table_apply(self, appname: str,  filename: str) -> bool:
        filename = appname + filename.split('.')[0]
        for table in self._get_table_log():
            if filename == table['filename']:
                if int(table['apply']):
                    return True
                else:
                    return False

    def append_table_in_log(self, appname: str, filename: str, apply_value: bool):
        filename = appname + filename.split('.')[0]
        if apply_value:
            apply = 1
        else:
            apply = 0
        self._query.custom_query(f"INSERT INTO `_tableapply` (`filename`, `apply`) VALUES ('{filename}', '{apply}')",
                                 dictionary=True)

    def _get_table_log(self) -> list:
        return self._query.custom_query('SELECT * FROM `_tableapply`', dictionary=True)

    def change_apply_status(self, filename: str, apply_value: bool):
        if apply_value:
            apply = 1
        else:
            apply = 0
        self._query.custom_query(f"UPDATE `_tableapply` SET `apply` = '{apply}' WHERE `_tableapply`.`filename` = '{filename}'")


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
