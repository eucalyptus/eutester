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
# author: clarkmatthew

'''
    Example:
    import eulogger
    self.logger = eulogger.Eulogger(name='euca')
    self.log = self.logger.log
    
    self.log.debug("This is a debug message")
    self.log.critical("this is a critical message")
'''

import os
import sys
import logging


class Eulogger(object):
    
    def __init__ (self,
                  name="eulogger",
                  log_level= "debug", 
                  fdebug ='%(message)s',
                  ferr = '%(funcName)s():%(lineno)d: %(message)',
                  logfile = "",
                  clear = False 
                  ):
                 
    # setup the logging This should eventually be done in it's own method probably...
        self.log_level = logging.__dict__.get(log_level.upper(),logging.DEBUG)
        self.logfile = os.path.join(logfile)
        self.ferr = ferr
        self.fdebug = fdebug
        self.clear = clear
        self.name = name
        
        self.formatter1 = logging.Formatter('[%(asctime)s] [EUTESTER] [%(levelname)s]: %(message)s')
        self.formatter2 = logging.Formatter('[%(asctime)s] [EUTESTER] [%(levelname)s] [%(filename)s:%(funcName)s():%(lineno)d]: %(message)s')
        self.formatter3 = logging.Formatter(self.name+':%(funcName)s():%(lineno)d: %(message)s')
        self.formatter4 = logging.Formatter('%(message)s')
        

        self.log = logging.getLogger(self.name)
        self.log.setLevel(self.log_level)
        
        if self.log.handlers != []:
            return 
        
        #now add the locations will log to by adding handlers to our logger...
        self.outhdlr = logging.StreamHandler(sys.stdout)
        self.outhdlr.setFormatter(self.formatter1)
        self.log.addHandler(self.outhdlr)
        
        if (self.logfile != ""):
            #to log to a file as well add another handler to the logger...
            if (self.clear):
                os.remove(self.logfile)
            filehdlr = logging.FileHandler(self.logfile)
            filehdlr.setFormatter(str(self.ferr))
            self.log.addHandler(filehdlr)


