from os import error
from threading import Thread, Lock

from Loader import Loader
from Parser import Parse
from multiprocessing import Queue
import threading
import time

# Global variable to hold the value of the all identifiers
IDs = tuple()

def parse_file(file_name, record_queue):
    
    start_time = time.time()

    try:
        parseFile = Parse()
        parseFile = parseFile.create_parser(file_name, record_queue)
        parseFile.read()
    except Exception as e:
        print(f'Corrupted or incomplete:  {e}')
    print(f"parse_file() took {time.time() - start_time} seconds")

        
    

def insert_file(parse_thread, record_queue, db_name):
    global IDs
    start_time = time.time()

    try:
        Loader.reset_instance() # Insure a new instance every time
        loader = Loader(parse_thread, record_queue, db_name)
    
        IDs = loader.insert_data()

    except Exception as e:
        print(f'Corrupted or incomplete:  {e}')
    print(f"insert_file() took {time.time() - start_time} seconds")

def main(file_name, db_name):
        
    global IDs
    
    IDs = tuple() # Reinitialize and empty bafore any parsing attempt
    
    record_queue = Queue()

    parse_thread = Thread(target=parse_file, args=(file_name, record_queue, ))
    parse_thread.daemon = False
    parse_thread.start()

    print(f"Parse Thread ID: {parse_thread.ident}")

    insert_thread = Thread(target=insert_file, args=(parse_thread, record_queue, db_name, ))
    insert_thread.daemon = False
    insert_thread.start()

    print(f"Insert Thread ID: {insert_thread.ident}")

    parse_thread.join()
    insert_thread.join()
    print(f"wafermap Thread ID: {threading.get_ident()}")
    print("IDs: ",IDs)
    return IDs

if __name__ == "__main__":
    main("stdf1.stdf", "database.db")
   