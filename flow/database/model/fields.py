from enum import Enum


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
            return f"ForeignKey(fk='{self.fk.lower()}', fnull={self.fnull}, " \
                   f"on_delete=fields.{self.on_delete}, on_update=fields.{self.on_update}, rel_name='{self.rel_name}')"
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


class UndefinedField(_Field):
    def __init__(self):
        super().__init__()
        self.fk = None


class DefaultModelFields:
    fields = {
        'id': AutoIncrementField()
    }
