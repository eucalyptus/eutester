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

import json
import argparse
import os
import re
import sys
import time
import commands
import tarfile
import urllib2
import cStringIO
from tar_utils import Local_Tarutils
from tar_utils import Http_Tarutils
#from eutester.machine import Machine



'''
class file():
    @classmethod
    def from_json(self, json):
        parse json here?
         
    def to_json:
        output json here? 
    def get_path(self):
        tbd
    def print_path(self):
        tbd
    def verify_md5(self):
        tbd
    def get_md5(self):
        tbd
    def download(self):
        tbd
    type
    uri
    name 
    checksum
    date
    version
    size
    
class users():
    @classmethod
    def from_json(self, json):
        parse json here?
         
    def to_json:
        output json here? 
    
    name
    login
    groups
    homedir

class packages():
    @classmethod
    def from_json(self, json):
        parse json here?
         
    def to_json:
        output json here? 
    list
    file
    
class hypervisors():
    @classmethod
    def from_json(self, json):
        parse json here?
         
    def to_json:
        output json here? 
    xen
    kvm
    vmware
    
class image_set():
    @classmethod
    def from_json(self, json):
        parse json here?
         
    def to_json:
        output json here? 
    roofs = file()
    ramdisk = file()
    kernel = file()
    
    
class os_info():
    xen = image_set()
    kvm = image_set()
    
'''

    

class emi_image_set():
    def __init__(self, uri, headersize=512, manifestname='manifest.json'):
        self.uri = uri
        self.manifestname=manifestname
        self.tar = self.get_tar_file(self.uri, headersize=headersize)
    def sys(self, cmd, listformat=True):
        status,output = commands.getstatusoutput(cmd)
        if status != 0:
            raise Exception('sys, cmd"'+str(cmd)+'" failed, code:'+str(status)+', output:'+str(output))
        else:
            if listformat:
                return str(output).splitlines()
            else:
                return str(output)
        
    def found(self,cmd,string):
        out = self.sys(cmd)
        if re.search(string, out):
            return True
        else:
            return False
        
    def get_tar_file(self,uri, headersize=512):
        if re.search('http://', uri):
            return Http_Tarutils(uri, headersize=headersize)
        else:
            return Local_Tarutils(uri, headersize=headersize)
        
        
    def extract_file(self, fpath, destpath=None):
        return self.tar.extract_member(fpath, destpath=destpath)
        
        
    def list_tar_contents(self):
        return self.tar.list()
    
    
    def extract_all(self, destdir=None):
        return self.tar.extract_member(destpath=destdir)
    

    def get_manifest(self):
        print "getting manifest"
        
        
        
