from flow.database.connector import DbConnector
from flow.database.models import _Field, fields_to_sql


class DbQuery:
    """
    Database queries.
    """
    def __init__(self):
        # The object to send the request.
        # Returns the response as a list or an empty list.
        self._query = DbConnector().query
        self._db_name = DbConnector().get_db_name()

    def get_db_name(self):
        return self._db_name

    def custom_query(self, query, db_connect=True, list_format=False, dictionary=False):
        return self._query(query, db_connect, list_format, dictionary)

    def show_databases(self) -> DbConnector.query:
        return self._query('SHOW DATABASES', db_connect=False, list_format=True)

    def create_table(self, table_name, fields: list[_Field]):
        self._query(f"CREATE TABLE `{self._db_name}`.`{table_name}` {fields_to_sql(fields)}")

    def create_field(self, table_name, field: _Field):
        self._query(f"ALTER TABLE `{table_name}` ADD {fields_to_sql(field)};")

    def delete_field(self, table_name, where: str):
        self._query(f"DELETE FROM `{table_name}` WHERE {where};")

    def delele_table(self, table_name):
        self._query(f"DROP TABLE `{self._db_name}`.`{table_name}`")

    def update_field(self, table_name, field: _Field):
        self._query(f"ALTER TABLE `{table_name}` CHANGE `{field.fname}` {fields_to_sql(field, brackets=False)};")

    def show_tables(self):
        return self._query('SHOW TABLES;', list_format=True)

    def insert_data(self, table_name, values: str):
        self._query(f"INSERT INTO `{table_name}` {values}")

    def select_from(self, table_name, select_field: str, where: str = '', list_format=True, dictionary=False):
        if where:
            return self._query(f"SELECT {select_field} FROM `{table_name}` WHERE {where};", list_format=list_format, dictionary=dictionary)
        else:
            return self._query(f"SELECT {select_field} FROM `{table_name}`;", list_format=list_format, dictionary=dictionary)

    def update_data(self, table_name, values: str, where: str):
        self._query(f"UPDATE `{table_name}` SET {values} WHERE {where}")

    def clear_table(self, table_name):
        self._query(f"TRUNCATE `{self._db_name}`.`{table_name}`")