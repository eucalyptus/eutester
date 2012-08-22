from eucaops import Eucaops
from eutester import euinstance, euvolume
import logging
from boto.ec2.snapshot import Snapshot
from boto.ec2.image import Image
import re
import time
import httplib
import unittest
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import EutesterTestResult
import testcases.cloud_user.images.eustoretestsuite

class WindowsTestSuite(EutesterTestCase):
    
    #Define the bytes per gig
    gig = 1073741824
    
        
        
    def __init__(self, 
                 tester=None, 
                 config_file='../input/2b_tested.lst', 
                 password="foobar", 
                 credpath=None, 
                 destpath='/tmp', 
                 url=None, 
                 zone=None, 
                 keypair=None, 
                 group=None, 
                 emi=None,
                 time_per_gig = 300,
                 eof=True,
                 work_component=None):
        
        if tester is None:
            self.tester = Eucaops( config_file=config_file,password=password,credpath=credpath)
        else:
            self.tester = tester
        self.tester.exit_on_fail = eof
        
        self.component = work_component or self.tester.clc
        
        self.destpath = str(destpath)
        self.time_per_gig = time_per_gig
        self.emi = emi
        self.credpath=credpath
        self.url = url
        
        
        #create some zone objects and append them to the zonelist
        if zone is not None:
            self.zone = eustoretestsuite.TestZone(zone)
            self.zonelist.append(self.zone)
        else: 
            for zone in self.tester.service_manager.partitions.keys():
                partition = self.tester.service_manager.partitions.get(zone)
                tzone = TestZone(partition)
                self.zonelist.append(tzone)
                self.multicluster=True
        #Setup our security group for later use
        if (group is not None):
            self.group = group
        else:
            group_name='EbsTestGroup'
            
            try:
                self.group = self.tester.add_group(group_name)
                self.tester.authorize_group_by_name(self.group.name)
                self.tester.authorize_group_by_name(self.group.name,protocol="icmp",port=-1)
            except Exception, e:    
                raise Exception("Error when setting up group:"+str(group_name)+", Error:"+str(e))   
        #Setup the keypairs for later use
        try:
            if (keypair is not None):
                self.keypair = keypair
            else:     
                keys = self.tester.get_all_current_local_keys() 
                if keys != []:
                    self.keypair = keys[0]
                else:
                    self.keypair = keypair = self.tester.add_keypair('ebs_test_key-' + str(time.time()))
        except Exception, ke:
            raise Exception("Failed to find/create a keypair, error:" + str(ke))
        
    
    def getRemoteImageSize(self, url, unit=gig):
            
            #Get the remote file size from the http header of the url given
            try:        
                url = url.replace('http://','')
                host = url.split('/')[0]
                path = url.replace(host,'')
                self.debug("get_remote_file, host("+host+") path("+path+")")
                conn=httplib.HTTPConnection(host)
                conn.request("HEAD", path)  
                res=conn.getresponse()
                fbytes=int(res.getheader('content-length'))
                self.debug("content-length:"+str(fbytes))
                if fbytes == 0:
                    rfsize = 0
                else:
                    rfsize= ( ((fbytes/unit)+1) or 1)
                self.debug("Remote file size: "+ str(rfsize) + "g")
            except Exception, e:
                self.debug("Failed to get remote file size...")
                raise e
            finally:
                if conn:
                    conn.close()
            return rfsize

    def wget_image(self,url,path=None, component=None, user=None, password=None, retryconn=True, timepergig=300):
        machine = component or self.component
        if path is None and self.destpath:
            path = self.destpath
        size = self.getRemoteImageSize(url)
        timeout = size * time_per_gig
        machine.wget_remote_image(self,url,path=path, user=user, password=password, retryconn=retryconn, timeout=timeout)
        return size
        
        
    def bundle_image(self,path,component=None, timeout=600):
        machine = component or self.component
        skey = self.tester.get_secret_key()
        akey = self.tester.get_access_key()
        cmd = 'euca-bundle-image -a '+str(akey) + ' -s ' + str(skey) + ' -i '+ str(path)
        out = machine.cmd(cmd, timeout=timeout)
        if out['statuscode'] != 0:
            raise Exception('bundle_image "'+str(path)+'" failed. Errcode:'+str(out['statuscode']))
        for line in out['output']:
            line = str(line)
            if re.search('Generating manifest',line):
                manifest = line.split()[2]
                break
        self.debug('bundle_image:'+str(path)+'. manifest:'+str(manifest))
        return manifest
    
    def upload_bundle(self, manifest, component=None, bucketname=None, timeout=600, uniquebucket=True):
        bname = ''
        machine = component or self.component
        manifest = str(manifest)
        self.debug('Attempting to upload_bundle:'+str(manifest)+", bucketname:"+str(bucketname))
        if bucketname:
            basename = bucketname
        else:
            basename = str(manifest.replace('.manifest.xml','')).split('/')[len(mlist)-1]
        if uniquebucket:
            bx = 0 
            bname = basename+"test"+str(bx)
            while self.tester.get_bucket_by_name(bname) is not None:
                bx += 1
                bname = basename+"test"+str(bx)
                
        skey = self.tester.get_secret_key()
        akey = self.tester.get_access_key()
        cmd = 'euca-upload-bundle -a '+str(akey) + ' -s ' + str(skey) + ' -b '+ str(bname) + ' -m ' + str(manifest)
        out = machine.cmd(cmd, timeout=timeout)
        if out['statuscode'] != 0:
            raise Exception('upload_bundle "'+str(manifest)+'" failed. Errcode:'+str(out['statuscode']))
        for line in out['output']:
            line = str(line)
            if re.search('Uploaded image',line):
                upmanifest = line.split()[3]
                break
        self.debug('upload_image:'+str(manifest)+'. manifest:'+str(upmanifest))
        return upmanifest
    
    def register_image(self,manifest,component=None):
        machine = component or self.component
        manifest = str(manifest)
        self.debug('register_image:'+str(manifest))
        cmd = 'euca-upload-bundle -a '+str(akey) + ' -s ' + str(skey) + ' -m ' + str(manifest)
        out = machine.cmd(cmd, timeout=timeout)
        if out['statuscode'] != 0:
            raise Exception('register_image "'+str(manifest)+'" failed. Errcode:'+str(out['statuscode']))
        for line in out['output']:
            line = str(line)
            if re.search('IMAGE',line):
                emi = line.split()[1]
                break
        self.debug('upload_image:'+str(manifest)+'. emi:'+str(emi))
        return emi
    
    
        
    