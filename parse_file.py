from inspect import _void
import time
import struct
import logging
import datetime

from DieInfo import DieInfo


class ParseFile():
    # class variable _instance will keep track of the lone object instance
    _instance = None

    def __init__(self, file_name, record_queue) -> None:
        super().__init__()
        self.record_queue = record_queue
        self._file_name = file_name
        self.record_sub_type = self.record_type = 0
        self.record = bytearray()  #faster processing
        self.logger = logging.getLogger(__name__)
        self.sites = {}
        self.dies_counter = 0
        logging.basicConfig(level=logging.DEBUG, filename='logs\waferMap.log')

    def extract_pir(self):
        self.dies_counter += 1
        site_num = self.record[1]
        self.sites[site_num] = DieInfo(self.dies_counter, site_num)
        return

    def extract_prr(self):
        #Extract site_num    U*1
        site_num = self.record[1]

        #Extract PassFail bit from PART_FLG and store the value as a string
        PART_FLG = self.record[2]
        PassFail = False if ((PART_FLG & 0b00001000) > 0) else True    #PassFail bit [3] forth bit

        #Extract HW and SW bin  U*2
        HARD_Bin = self.record[5] + (self.record[6] << 8)
        SOFT_Bin = self.record[7] + (self.record[8] << 8)

        #Extract X_COORD  Y_COORD I*2
        X_COORD, Y_COORD = struct.unpack('<hh', self.record[9:13])

        self.sites[site_num].set_info((HARD_Bin, SOFT_Bin, X_COORD, Y_COORD, PART_FLG, PassFail))
        self.record_queue.put(("die_info", self.sites[site_num]))
        del self.sites[site_num]

        return

    def extract_ptr(self):
        #Extract test_num   U*4
        test_num = int.from_bytes(self.record[0:4], byteorder='little', signed=False)

        #Extract site_num   U*1
        site_num = self.record[5]

        #Extract PF bit from PARAM_FLG  B*1
        PARAM_FLG = self.record[7]

        #Extract Result R*4
        result = struct.unpack('<f', self.record[8:12])[0]

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

        self.sites[site_num].add_test_result((test_num, LO_LIMIT, HI_LIMIT, result ,PARAM_FLG))

    def extract_data(self):
        if self.record_name == "MIR":
            #Extract LotID  C*n
    
            #Byte at index 15 contains LotID size 
            self.LotID = self.record[16 : 16 + self.record[15]]  #extract LotID as a bytearray
            self.LotID = self.LotID.decode('utf-8') #Stringify LotID
            #print(self.LotID)
        elif self.record_name == "WIR":
            self.isWIR = True
            
            #Extract WaferID  C*n
            self.WaferID = self.record[7 : 7 + self.record[6]] 
            self.WaferID = self.WaferID.decode('utf-8')
            #print(self.WaferID)
            self.record_queue.put(("wafer_info", self.LotID, self.WaferID))
            if self._wafer_config:
                self.record_queue.put(("wafer_config", *self._wafer_config))

        elif self.record_name == "WCR":
            #extract WF_UNITS: for wafer and die size calculations
            WF_UNITS = self.record[12]

            #extract wafer_size [wafer diameter] die height and width  R*4
            self.wafer_size, self.DIE_HT, self.DIE_WID = struct.unpack('<fff', self.record[0:12])
            
            self.wafer_size *= WF_UNITS
            self.DIE_HT *= WF_UNITS
            self.DIE_WID *= WF_UNITS
            
            #extract orientation of wafer flat  C*1
            self.WF_FLAT = chr(self.record[13])

            # Extract Center_X and Center_Y   I*2
            self.Center_X, self.Center_Y = struct.unpack('<hh', self.record[14:18])

            # Extract POS_X and POS_Y C*1
            self.POS_X = chr(self.record[18])
            self.POS_Y = chr(self.record[19])

            self._wafer_config = (self.wafer_size, self.DIE_HT, self.DIE_WID , self.WF_FLAT, self.Center_X, self.Center_Y, self.POS_X, self.POS_Y)
            return

    def read(self):
        start = time.time()
        
        #mark the begining of each new log
        self.logger.info(f'New Log       Date: {datetime.datetime.now()}')
        with open(self._file_name, "rb") as f:
            #itterate over file until a MRR record is met
            while header := f.read(4):
                #decompose the header into size, type, and sub type
                self.record_size = int.from_bytes(header[0:2], byteorder='little')
                self.record_type = header[2]
                self.record_sub_type = header[3]

                self.record = f.read(self.record_size)

                if self.record_type == 0 and self.record_sub_type == 10:
                    self.record_name = "FAR"
                    self.extract_data()
                elif self.record_type == 1 and self.record_sub_type == 10:
                    self.record_name = "MIR"
                    self.extract_data()
                elif self.record_type == 2 and self.record_sub_type == 10:
                    self.record_name = "WIR"
                    self.extract_data()
                elif self.record_type == 2 and self.record_sub_type == 30:
                    self.record_name = "WCR"
                    self.extract_data()
                elif self.record_type == 5 and self.record_sub_type == 10:
                    self.record_name = "PIR"
                    self.extract_pir()
                elif self.record_type == 15 and self.record_sub_type == 10:
                    self.record_name = "PTR"
                    self.extract_ptr()
                elif self.record_type == 5 and self.record_sub_type == 20:
                    self.record_name = "PRR"
                    self.extract_prr()
                elif self.record_type == 1 and self.record_sub_type == 20:
                    self.record_name = "MRR"
                    

                    

        end = time.time()
        self.logger.info(f'Execution time: {end - start} seconds')
        self.logger.info(f'-------------------------------------------------------------====-------------------------------------------------------------')



