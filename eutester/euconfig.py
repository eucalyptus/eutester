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
import os
import ConfigParser

class Section():
    def __init__(self, name, config_parser, strip='"'):
        self.name = name
        self.config_parser = config_parser
        self.strip = strip
        self.create_attributes_for_section()


    def create_attributes_for_section(self):
        for item in self.config_parser.items(self.name):
            item_name = item[0]
            if self.strip:
                value =  str(item[1]).strip(self.strip)
            else:
                value = item[1]
            self.add_item(item_name,value)

    def add_item(self, config_item_name, value):
        setattr(self, config_item_name, value)



class EuConfig():
    
    def __init__(self,
                 filename='../input/2btested.lst',
                 config_lines=None,
                 debugmethod=None,
                 verbose=False,
                 default_section_name='DEFAULTS',
                 make_section_attrs=True,
                 strip_values = '"'):
        self.debugmethod = debugmethod
        self.make_section_attrs = make_section_attrs
        self.strip_values = strip_values
        self.filename = filename
        self.default_section_name = default_section_name or os.path.basename(self.filename)
        self.verbose = verbose
        
        #read the file into a list of lines
        self.lines = config_lines or self.read_config_file(filename)
        
        #parse out any legacy config into a separate buffer
        self.legacybuf = self.get_legacy_config()
        
        #parse out remaining non-legacy config into another buffer
        self.configbuf = self.get_config_buf()
        
        #create our configParser object using the config buffer
        self.config = None
        self.populate_config_parser_from_buf()


        
        
    def get(self,section,key):
        return self.config.get(section,key)


    def populate_config_parser_from_buf(self,
                                        buf=None,
                                        default_section_name=None,
                                        make_section_attrs=None,
                                        strip_values=None):
        #create our configParser object using the config buffer
        default_section_name = default_section_name or self.default_section_name
        make_section_attrs = make_section_attrs or self.make_section_attrs
        strip_values = strip_values or self.strip_values
        self.config = ConfigParser.RawConfigParser()
        buf = buf or self.configbuf
        default_section_name=default_section_name or self.default_section_name
        try:
            self.config.readfp(io.BytesIO(buf))
        except ConfigParser.MissingSectionHeaderError, mshe:
            #A file with key pair format but no sections may have been fed in...?
            if default_section_name:
                buf = '[' + str(default_section_name) + ']\n' + str(buf)
                return self.create_config_parser_from_buf(buf=buf, create_default_section=False)
            else:
                raise mshe
        if make_section_attrs:
            self.make_sections(strip=strip_values)

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
            if re.match("^MEMO\s+", line):
                line = '['+str(line).strip()+']\n'
            if re.match("^END_MEMO", line):
                continue
            #read file until first section  header
            if not start:
                if re.match("^\[", line):
                    self.debug("Found fist section header, start reading in config buff")
                    buf=buf+line
                    start=True
            else:
                if re.match("^\s*#",line) or re.match("^\s+$",line) or not re.search("=",line):
                    self.debug("Ignoring line for config buf:"+str(line))
                    continue
                else:
                    self.debug("Adding line to config buff:"+str(line))
                    if not line.endswith('\n'):
                        line = line+"\n"
                    buf=buf+line              
        return buf
                

    def make_sections(self, strip='"'):
        '''
        Creates section objects within this euconfig instance.
        Example: The machine classes may have a file called eucalyptus_conf and create a section '[eucalyptus_conf]'
        This will add the section to self.config.sections, as well as create a Section() object with attributes
        for each item which contain that item's value.
        For a machine called 'clc' values out of this config file can be access like this...
            >print clc.config.eucalyptus_conf.hypervisor
            > kvm

            >print clc.config.eucalyptus_conf.cloud_opts
            >-Debs.storage.manager=SANManager -Debs.san.provider=NetappProvider --debug
        '''
        for section in self.config.sections():
                self.debug('Adding section:' + str(section))
                new_section = Section(section,self.config, strip=strip)
                setattr(self, section, new_section)

    
        
            
        
        