from mysql.connector import connect, Error
from fconfig.fsettings import DATABASE as DB


class DbConnector:
    """The class is designed to connect to the database."""
    def __init__(self, host: str = DB['host'], user: str = DB['user'], password: str = DB['password'], database: str = DB['database']):
        self._host = host
        self._user = user
        self._password = password
        self._database = database

        self._db_check()

    def connect(self, db_connect: bool = True) -> connect:
        """
        Connection for working with the database.

        :param db_connect:
        :type db_connect: bool
        :return: connect
        """
        try:
            if db_connect:
                conn = connect(
                    host=self._host,
                    user=self._user,
                    password=self._password,
                    database=self._database
                )
            else:
                conn = connect(
                    host=self._host,
                    user=self._user,
                    password=self._password,
                )
            return conn
        except Error as e:
            raise e

    def query(self, query_string: str, db_connect: bool = True, list_format=False, dictionary=False) -> list:
        """
        The method executes a database query and returns the query data.

        :param query_string: Request text.
        :param db_connect: Connection type.
        :param list_format: The format type for outputting data from the query.
        :param dictionary: Output the query result as a dictionary.
        :return: list
        """
        conn = self.connect(db_connect)
        querydata = []
        try:
            with conn.cursor(dictionary=dictionary) as cursor:
                cursor.execute(query_string)
                for data in cursor:
                    if list_format:
                        querydata.append(data[0])
                    else:
                        querydata.append(data)
            conn.commit()
        except Error as e:
            raise e
        conn.close()
        if not querydata:
            querydata = []
        return querydata

    def get_db_name(self):
        return self._database

    def _db_check(self):
        all_db_name = self.query('SHOW DATABASES', db_connect=False, list_format=True)
        if not self._database in all_db_name:
            self.query(f'CREATE DATABASE {self._database}', db_connect=False)