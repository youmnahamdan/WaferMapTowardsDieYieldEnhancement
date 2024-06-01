from threading import Thread, Lock

from Loader import Loader
from Parser import Parse
from multiprocessing import Queue

import time

# Global variable to hold the value of the all identifiers
IDs = tuple()

def parse_file(file_name, record_queue):
    start_time = time.time()

    parseFile = Parse()
    parseFile = parseFile.create_parser(file_name, record_queue)
    parseFile.read()

    print(f"parse_file() took {time.time() - start_time} seconds")

def insert_file(parse_thread, record_queue, db_name):
    global IDs
    start_time = time.time()

    loader = Loader(parse_thread, record_queue, db_name)
    loader.insert_data()
    
    with Lock():
        IDs = loader.get_IDs()

    print(f"insert_file() took {time.time() - start_time} seconds")

def main(file_name, db_name):
    global IDs
    record_queue = Queue()

    parse_thread = Thread(target=parse_file, args=(file_name, record_queue, ))
    parse_thread.daemon = False
    parse_thread.start()

    insert_thread = Thread(target=insert_file, args=(parse_thread, record_queue, db_name, ))
    insert_thread.daemon = False
    insert_thread.start()

    parse_thread.join()
    insert_thread.join()

    #print("Done!")
    return IDs

if __name__ == "__main__":
    main("demofile.stdf", "database.db")
   