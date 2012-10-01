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
        
        
        
