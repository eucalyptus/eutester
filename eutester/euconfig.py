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
# Author: matt.clark@eucalyptus.com
'''
Created on May 11, 2012
@author: clarkmatthew

Simple utility to read a given config file and parse out the configuration. 
Uses python's Config Parser but includes some utils to support legacy config files
To use this utility, the config file given must use the following format:
[prefix]key=value

example:
Add the following lines to a file called /tmp/config.txt
Note: 
This example is using the legacy config with ip, distro, and component info. 

>cat /tmp/config.txt
    1.1.1.1   CENTOS  5.7     64      REPO [CLC WS]
    1.1.1.2   CENTOS  5.7     64      REPO [NC00]
    
    [mytest]
    volumes=2
    image=centos.img
    
    [joestest]
    image=ubuntu.img
    name=joe
    iterations=3
    output=/tmp/joesoutput.txt


To retrieve config info from this file from within a test:
>conf = EuConfig(filename='/tmp/config.txt')
>myimage = conf.get_config('mytest','image')
>joesimage = conf.get('joestest','image')
>
>print myimage
 centos.img
 
>print conf.legacybuf
 1.1.1.1   CENTOS  5.7     64      REPO [CLC WS]
 1.1.1.2   CENTOS  5.7     64      REPO [NC00]


'''
import re
import io
import ConfigParser


class EuConfig():
    
    def __init__(self,filename='../input/2btested.lst', debugmethod=None, verbose=False):
        self.filename = filename
        self.verbose = verbose
        
        #read the file into a list of lines
        self.lines = self.read_config_file(filename)
        
        #parse out any legacy config into a separate buffer
        self.legacybuf = self.get_legacy_config()
        
        #parse out remaining non-legacy config into another buffer
        self.configbuf = self.get_config_buf()
        
        #create our configParser object using the config buffer
        self.config = ConfigParser.RawConfigParser()
        self.config.readfp(io.BytesIO(self.configbuf))
        
        
    def get(self,section,key):
        return self.config.get(section,key)
    
    
    def read_config_file(self,filename):
        cfile = open(filename,'r')
        lines = cfile.readlines()
        cfile.close()
        return lines
    
        
    def debug(self, msg):
        if self.verbose:
            if self.debugmethod is not None:
                self.debugmethod(str(msg))
            else:
                print(str(msg))
        
        
    def get_legacy_config(self, lines=None):
        '''
        Gather all lines  from the given config until a section header is reached
        In order to be backwards compatible with previous configuration files
        will return a buffer of file read until the first section header
        '''
        buf=""
        if lines is None:
            lines = self.lines
        for line in lines:
            #read file until first section  header
            if re.match("^\[", line):
                self.debug("Found section header, returning buf")
                return buf
            else:
                #filter out comments and blank lines
                if re.match("^\s+#",line) or re.match("^\s+$",line):
                    self.debug("Ignoring legacy line:"+str(line))
                    continue
                else:
                    self.debug("Adding line to legacy buf:"+str(line))
                    buf=buf+line
        return buf
    
    
    def get_config_buf(self,lines=None): 
        '''
        Gather config lines into list. 
        To support legacy config, will exclude all lines read prior to detecting a section header. 
        Will ignore blank lines and lines starting with "#" representing comments 
        '''
        buf=""
        start=False
        if lines is None:
            lines = self.lines
        for line in lines:
            #read file until first section  header
            if not start:
                if re.match("^\[", line):
                    self.debug("Found fist section header, start reading in config buff")
                    buf=buf+line
                    start=True
            else:
                if re.match("^\s+#",line) or re.match("^\s+$",line):
                    self.debug("Ignoring line for config buf:"+str(line))
                    continue
                else:
                    self.debug("Adding line to config buff:"+str(line))
                    buf=buf+line              
        return buf
                
    
    
        
            
        
        