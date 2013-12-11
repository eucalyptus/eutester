#!/usr/bin/python
# -*- coding: utf-8 -*-
# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
__author__ = 'clarkmatthew'

import re

class San_Volume_Info():
    def __init__(self, volumeid,  info_dict, san_client):
        self.__dict__ = self.convert_numbers_in_dict(info_dict)
        self.volumeid = volumeid
        self.san_client = san_client
        self.debug = san_client.debug


    def update(self):
        info = self.san_client.get_san_volume_info_by_id(self.volumeid)
        self.__dict__ = self.convert_numbers_in_dict(info)

    def convert_numbers_in_dict(self, dict):
        #convert strings representing numbers to ints
        for key in dict:
            if (re.search("\S", str(dict[key])) and not re.search("\D", str(dict[key]))):
                dict[key] = long(dict[key])
        return dict

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



