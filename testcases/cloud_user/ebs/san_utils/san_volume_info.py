__author__ = 'clarkmatthew'

import re

class San_Volume_Info():
    def __init__(self, volumeid,  info_dict, san_connection):
        self.__dict__ = self.convert_numbers_in_dict(info_dict)
        self.volumeid = volumeid
        self.san_connection = san_connection
        self.debug = san_connection.debug


    def update(self):
        info = self.get_volume_info(self.volumeid, self.san_connection)
        self.__dict__ = self.convert_numbers_in_dict(info)

    def convert_numbers_in_dict(self, dict):
        #convert strings representing numbers to ints
        for key in dict:
            if (re.search("\S", str(dict[key])) and not re.search("\D", str(dict[key]))):
                dict[key] = long(dict[key])
        return dict

    def get_volume_info(self, volumeid, san_connection):
        return self.san_connection.get_info_for_volume_id(self.volumeid)


    def print_self(self, printmethod=None):
        '''
        formats and prints
        '''
        printmethod = printmethod or self.debug
        buf = "\n"
        longest_key = 0
        for key in self.__dict__:
            if len(key) > longest_key:
                longest_key = len(key)
        for key in self.__dict__:
            buf += str(key).ljust(longest_key) + " -----> :" + str(self.__dict__[key]) + "\n"
        printmethod(buf)



