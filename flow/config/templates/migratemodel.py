class MigrateModel:
    # simple table

    # TODO empty exceptions
    default_fields = [

    ]
    name: str = ''
    fields: list[_Field] = [
        IntField('test')
    ]


class_name = ''


mgr_str = f"""class {class_name}:
# simple table

default_fields = [

]
name = {class_name}
fields = [

]"""