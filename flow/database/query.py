from flow.database.connector import DbConnector


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

    def create_table(self, table_name, fields: str):
        self._query(f"CREATE TABLE `{self._db_name}`.`{table_name}` {fields}")

    def create_column(self, table_name, column: str):
        self._query(f"ALTER TABLE `{table_name}` ADD {column};")

    def delete_field(self, table_name, where: str):
        self._query(f"DELETE FROM `{table_name}` WHERE {where};")

    def delete_column(self, table_name, column_name):
        self._query(f"ALTER TABLE `{table_name}` DROP `{column_name}`;")

    def delele_table(self, table_name):
        self._query(f"DROP TABLE `{self._db_name}`.`{table_name}`")

    def update_table_attr(self, table_name, field_name: str, values: str):
        self._query(f"ALTER TABLE `{table_name}` CHANGE `{field_name}` {values};")

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

    def add_fk(self, table_name, fk_field: str, ref_table_name: str, ref_col_name: str, on_delete: str, on_update: str):
        self._query(f"ALTER TABLE `{table_name}` ADD FOREIGN KEY (`{fk_field}`) "
                    f"REFERENCES `{ref_table_name}`(`{ref_col_name}`) ON DELETE {on_delete} ON UPDATE {on_update}; ")

    def show_additional_fk_info(self, relation_name):
        return self._query(f"SELECT `CONSTRAINT_NAME`, `DELETE_RULE`, `UPDATE_RULE`, `TABLE_NAME`, `REFERENCED_TABLE_NAME`"
                           f" FROM `INFORMATION_SCHEMA`.`REFERENTIAL_CONSTRAINTS` WHERE `CONSTRAINT_NAME` = '{relation_name}';", dictionary=True)

    def show_fk_relation_name(self, column_name):
        return self._query(f"SELECT `CONSTRAINT_NAME` FROM `INFORMATION_SCHEMA`.`KEY_COLUMN_USAGE` "
                           f"WHERE `REFERENCED_TABLE_NAME` IS NOT NULL AND `COLUMN_NAME` = '{column_name}';", list_format=True)

    def delete_relation(self, table_name, relation_name):
        self._query(f'ALTER TABLE {self._db_name}.{table_name} DROP FOREIGN KEY {relation_name}')
