from threading import Thread, Lock
from Loader import Loader
from Parser import Parse
from multiprocessing import Queue
import threading
import time

# Global variable to hold the value of the all identifiers
IDs = tuple()

def parse_file(file_name, record_queue):
    """
    Call read method to read and parse STDF files using a ParseFile instance 
    returned from create_parser method.
    
    Args:
    file_name [string]: file path
    record_queue [Queue object]
    """
    
    start_time = time.time()

    try:
        # Create a Parse instance
        parseFile = Parse()
        
        # The method create_parser returns a ParseFile instance
        parseFile = parseFile.create_parser(file_name, record_queue)
        
        # Parse STDF file
        parseFile.read()
        
    except Exception as e:
        print(f'Corrupted or incomplete:  {e}')
    print(f"parse_file() took {time.time() - start_time} seconds")

        
    

def insert_file(parse_thread, record_queue, db_name):
    """
    Pop data from queue then insert into the database via insert_data function from Loader class.
    
    Args:
    parse_thread [Thread]
    record_queue [Queue object]
    db_name [string]
    """
    global IDs
    start_time = time.time()

    # Reset Loader instance into None to avoid issues at corrupted files
    Loader.reset_instance()
    
    try:
        # Create a Loader instance
        loader = Loader(parse_thread, record_queue, db_name)
        
        # Insert data
        loader.insert_data()
        
    except Exception as e:
        print(f'Corrupted or incomplete:  {e}')

    print(f"insert_file() took {time.time() - start_time} seconds")

def main(file_name, db_name):
        
    global IDs
    
    # Instantiate a Queue
    record_queue = Queue()

    # Start parse_file in a new Thread
    parse_thread = Thread(target=parse_file, args=(file_name, record_queue, ))
    
    # Insure no termination untill parsing is over
    parse_thread.daemon = False
    
    # Start parse_thread
    parse_thread.start()

    # Start insert_file in a new Thread
    insert_thread = Thread(target=insert_file, args=(parse_thread, record_queue, db_name, ))
    
    # Insure no termination untill insertion is over
    insert_thread.daemon = False
    
    # Start insert_thread
    insert_thread.start()

    # Join threads to main_thread when excecution is over
    parse_thread.join()
    insert_thread.join()

    #print("Done!")
    return IDs

if __name__ == "__main__":
    main("stdf1.stdf", "database.db")
   