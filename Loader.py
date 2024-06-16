import sqlite3
from sqlite3 import Error

class Loader:
    """Singleton class for interacting with a SQLite database."""

    # Class instance
    _instance = None
    
    # Constructor called for creatin new instances of the class
    def __new__(cls, parse_thread, record_queue, db_name):
        """Overrides the __new__ method to ensure singleton behavior."""
        if not cls._instance: # Make sure only one instance exists. 
            cls._instance = super().__new__(cls)
            cls._instance._parse_thread = parse_thread
            cls._instance._record_queue = record_queue
            cls._instance._db_name = db_name  
            cls._instance._conn = None
            cls._instance._connect_to_db() # Connect to the database
        
        # Return instance    
        return cls._instance 

    @classmethod
    def reset_instance(cls):
        """ Reset class instance to None. """
        cls._instance = None

    def _connect_to_db(self):
        """Connects to the SQLite database."""
        if not self._conn:  # Check only once
            self._conn = sqlite3.connect(self._db_name)
            self._cursor = self._conn.cursor()

    def retrieve_data(self, table_name, query=None, params=None):
        """
        Retrieves data from a table.

        Args:
            table_name: The name of the table to retrieve data from.
            query: Optional SQL query string (defaults to SELECT * FROM table_name).
            params: Optional tuple of parameters for the query (if used).

        Returns:
            A list of rows containing the retrieved data.
        """

        if not query:
            query = f"SELECT * FROM {table_name}"
        if params:
            self._cursor.execute(query, params)
        else:
            self._cursor.execute(query)
        return self._cursor.fetchall()

    def insert_data(self):
        """
        Inserts a data tuple to the database.
        
        Returns:
        IDs [tuple]: (MasterID, LotID, WaferID)
        """

        while self._parse_thread.is_alive():
            while not self._record_queue.empty():
                # Decompose records
                table_name, *record = self._record_queue.get()
                # Store identical SQL statements for batch insertion
                sql_statements = []

                if table_name == "wafer_info":
                    if not self.retrieve_data("wafer_info", query=f"SELECT * FROM wafer_info WHERE LotID = ? and WaferID = ?", params=(record[0], record[1])):
                        sql_params = record
                        column_placeholders = ', '.join('?' * len(sql_params))
                        sql_statements.append((sql_params, f"""INSERT INTO wafer_info (LotID, WaferID) VALUES ({column_placeholders})"""))

                elif table_name == "wafer_config":
                    sql_params = (self._wafer_id, record[0], record[1], record[2], record[3], record[4], record[5], record[6], record[7])
                    column_placeholders = ', '.join('?' * len(sql_params))
                    sql_statements.append((sql_params, f"""INSERT INTO wafer_config (MasterID, WaferSize, DieHeight, DieWidth, WaferFlat, CenterX, CenterY, PositiveX, PositiveY) VALUES ({column_placeholders})"""))
                
                elif table_name == "die_info":
                    die_num = record[0].get_number()
                    die_site = record[0].get_site()
                    die_info = record[0].get_info()
                    sql_params = (self._wafer_id,die_num,die_site, die_info[0], die_info[1], die_info[2], die_info[3], die_info[4], die_info[5])
                    column_placeholders = ', '.join('?' * len(sql_params))
                    sql_statements.append((sql_params, f"""INSERT INTO die_info (MasterID, DieID, SiteNum, HardwareBin, SoftwareBin, DieX, DieY, PartFlg, Passing) VALUES ({column_placeholders})"""))
                    for test_result in record[0].get_test_results():
                        sql_params = (self._wafer_id,die_num, test_result[0], test_result[1], test_result[2], test_result[3], test_result[4])
                        column_placeholders = ', '.join('?' * len(sql_params))
                        sql_statements.append((sql_params, f"""INSERT INTO test_results (MasterID, DieID, TestNumber, LowerLimit, UpperLimit, Result, TestFlag) VALUES ({column_placeholders})"""))

                try:
                    for sql_statement in sql_statements:
                        self._cursor.execute(sql_statement[1], sql_statement[0])

                    if table_name == "wafer_info":
                        self._conn.commit()
                        # Fetch MasterID from database
                        self._wafer_id = self.retrieve_data("wafer_info", query=f"SELECT MasterID FROM wafer_info WHERE LotID = ? and WaferID = ?", params=(record[0] , record[1]))[0][0]

                        # In case of reloading a pre-existing file we must delete it's data from db to avoid some constraints 
                        self.retrieve_data("wafer_config", "DELETE FROM wafer_config WHERE MasterID = ?", params=(self._wafer_id,))
                        self.retrieve_data("die_info", "DELETE FROM die_info WHERE MasterID = ?", params=(self._wafer_id,))
                        self.retrieve_data("test_info", "DELETE FROM test_results WHERE MasterID = ?", params=(self._wafer_id,))
                        
                except (Exception) as error:
                    self._conn.rollback()
                    print("Error while inserting data:", error)
                    return

        self._conn.commit()
        
        # Fetch WaferID, LoID, and MasterID
        IDs = self.retrieve_data("wafer_info", "SELECT * FROM wafer_info WHERE MasterID = ?", params=(self._wafer_id,))[0]

        # Close db connection
        self._cursor.close()
        self._conn.close()
        
        return IDs


    