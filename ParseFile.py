import time
import struct
import logging
import datetime

from DieInfo import DieInfo


class ParseFile():
    # Class variable _instance will keep track of the single object instance
    _instance = None

    def __init__(self, file_name, record_queue):
        super().__init__()
        self.record_queue = record_queue
        self._file_name = file_name
        self.record_sub_type = self.record_type = 0
        self.record = bytearray()  # Faster processing
        self.logger = logging.getLogger(__name__)
        self.sites = {}
        self.dies_counter = 0 # Acts as PartID or DieID
        logging.basicConfig(level=logging.DEBUG, filename='logs\waferMap.log')
    
    # Extract part information record
    def extract_pir(self):
        # Increment for each new die
        self.dies_counter += 1
        
        # Extract site_num    U*1
        site_num = self.record[1]
        
        # A dictionary to store site number with it's corresponding die
        self.sites[site_num] = DieInfo(self.dies_counter, site_num)

    # Extract part results record
    def extract_prr(self):
        # Extract site_num    U*1
        site_num = self.record[1]

        # Extract PassFail bit from PART_FLG
        PART_FLG = self.record[2]
        PassFail = False if ((PART_FLG & 0b00001000) > 0) else True    # Mask flag to extract the fourth bit

        # Extract HW and SW bin  U*2
        HARD_Bin = self.record[5] + (self.record[6] << 8)
        SOFT_Bin = self.record[7] + (self.record[8] << 8)

        # Extract X_COORD  Y_COORD I*2
        X_COORD, Y_COORD = struct.unpack('<hh', self.record[9:13])

        # Store results within DieInfo objects from inside the dictionary
        self.sites[site_num].set_info((HARD_Bin, SOFT_Bin, X_COORD, Y_COORD, PART_FLG, PassFail))
        
        # Put data into record_queue
        self.record_queue.put(("die_info", self.sites[site_num]))
        
        # Free memory
        del self.sites[site_num]

    # Extract parametric test results
    def extract_ptr(self):
        # Extract test_num   U*4
        test_num = int.from_bytes(self.record[0:4], byteorder='little', signed=False)

        # Extract site_num   U*1
        site_num = self.record[5]

        # Extract PF bit from PARAM_FLG  B*1
        PARAM_FLG = self.record[7]

        # Extract Result R*4
        result = struct.unpack('<f', self.record[8:12])[0]

        # Extract test limits.
        internal_offset = 12
        if self.record[12] > 0:
            internal_offset += self.record[12]
        internal_offset += 1

        if internal_offset < len(self.record):
            if self.record[internal_offset] > 0:
                internal_offset += self.record[internal_offset]
            internal_offset += 1

        internal_offset += 4

        LO_LIMIT, HI_LIMIT = None, None
        if internal_offset < len(self.record):
            LO_LIMIT, HI_LIMIT = struct.unpack('<ff', self.record[internal_offset:internal_offset+8])

        # Store test results related to currect site number
        self.sites[site_num].add_test_result((test_num, LO_LIMIT, HI_LIMIT, result ,PARAM_FLG))

    # Extract master information record, wafer information record, and wafer configuration record
    def extract_data(self):
        if self.record_name == "MIR":
            # Extract LotID  C*n starting from index 15 where ID size is stored
            self.LotID = self.record[16 : 16 + self.record[15]]  #extract LotID as a bytearray
            self.LotID = self.LotID.decode('utf-8') #Stringify LotID

        elif self.record_name == "WIR":
            # Extract WaferID  C*n
            self.WaferID = self.record[7 : 7 + self.record[6]] 
            self.WaferID = self.WaferID.decode('utf-8')
            
            # Put record in queue
            self.record_queue.put(("wafer_info", self.LotID, self.WaferID))
            
            if self._wafer_config:
                self.record_queue.put(("wafer_config", *self._wafer_config))

        elif self.record_name == "WCR":
            # Extract WF_UNITS: for wafer and die size calculations
            WF_UNITS = self.record[12]

            # Extract wafer_size [wafer diameter] die height and width  R*4
            self.wafer_size, self.DIE_HT, self.DIE_WID = struct.unpack('<fff', self.record[0:12])
            
            # Calculate dimensions
            self.wafer_size *= WF_UNITS
            self.DIE_HT *= WF_UNITS
            self.DIE_WID *= WF_UNITS
            
            # Extract orientation of wafer flat  C*1
            self.WF_FLAT = chr(self.record[13])

            # Extract Center_X and Center_Y   I*2
            self.Center_X, self.Center_Y = struct.unpack('<hh', self.record[14:18])

            # Extract POS_X and POS_Y C*1
            self.POS_X = chr(self.record[18])
            self.POS_Y = chr(self.record[19])

            self._wafer_config = (self.wafer_size, self.DIE_HT, self.DIE_WID , self.WF_FLAT, self.Center_X, self.Center_Y, self.POS_X, self.POS_Y)
            return
    # Parse STDF File
    def read(self):
        start = time.time()
        
        # Log parsing attempts
        self.logger.info(f'New Log       Date: {datetime.datetime.now()}')
        
        # Open file
        with open(self._file_name, "rb") as f:
            
            # Read record header 
            while header := f.read(4):
                # Decompose header into size, type, and sub type
                self.record_size = int.from_bytes(header[0:2], byteorder='little')
                self.record_type = header[2]
                self.record_sub_type = header[3]

                # Read record
                self.record = f.read(self.record_size)
                
                # Extract data from each record depending on it's type
                if self.record_type == 0 and self.record_sub_type == 10:
                    # FAR record indicates the beggining of STDF files and contains no significant information
                    self.record_name = "FAR"
                    
                elif self.record_type == 5 and self.record_sub_type == 10:
                    # PIR contains the site number to which each die belongs
                    self.record_name = "PIR"
                    self.extract_pir()

                elif self.record_type == 15 and self.record_sub_type == 10:
                    # PTR record holds test related information
                    self.record_name = "PTR"
                    self.extract_ptr()

                elif self.record_type == 5 and self.record_sub_type == 20:
                    # PRR record contains die related information, and it appears after PTR records
                    self.record_name = "PRR"
                    self.extract_prr()
                
                elif self.record_type == 1 and self.record_sub_type == 10:
                    # MIR record contains Lot ID
                    self.record_name = "MIR"
                    self.extract_data()

                elif self.record_type == 2 and self.record_sub_type == 10:
                    # WIR contains Wafer ID to help identify each wafer
                    self.record_name = "WIR"
                    self.extract_data()

                elif self.record_type == 2 and self.record_sub_type == 30:
                    # WCR contains wafer related information
                    self.record_name = "WCR"
                    self.extract_data()        

                elif self.record_type == 1 and self.record_sub_type == 20:
                    # MRR record indicates the end of file
                    self.record_name = "MRR"
                    

                    

        end = time.time()
        self.logger.info(f'Execution time: {end - start} seconds')
        self.logger.info(f'-------------------------------------------------------------====-------------------------------------------------------------')



