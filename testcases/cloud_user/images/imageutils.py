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

from eucaops import Eucaops
from eutester import euinstance, euvolume
import logging
from boto.ec2.snapshot import Snapshot
from boto.ec2.image import Image
import re
import time
import httplib
import sys
import unittest
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import EutesterTestResult
from eutester.eutestzone import euTestZone
from eutester.sshconnection import SshCbReturn


class ImageUtils(EutesterTestCase):
    
    #Define the bytes per gig
    gig = 1073741824
    mb = 1048576
    kb = 1024
    
    
    def __init__(self, 
                 tester=None, 
                 config_file=None, 
                 password="foobar", 
                 credpath=None, 
                 destpath='/disk1/storage/',  
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
        self.credpath=credpath or self.tester.credpath
     

    def getHttpHeader(self, url):
        url = url.replace('http://','')
        host = url.split('/')[0]
        path = url.replace(host,'')
        self.debug("get_remote_file, host("+host+") path("+path+")")
        conn=httplib.HTTPConnection(host)
        conn.request("HEAD", path)  
        return conn.getresponse()
    
    
    
    def getHttpRemoteImageSize(self, url, unit=None): 
            '''
            Get the remote file size from the http header of the url given
            Returns size in GB unless unit is given. 
            '''
            unit = unit or self.__class__.gig
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

    def wget_image(self,url,destpath=None, component=None, user=None, password=None, retryconn=True, time_per_gig=300):
        machine = component or self.component
        if destpath is None and self.destpath is not None:
            destpath = self.destpath
        size = self.getHttpRemoteImageSize(url)
        if (size <  machine.get_available(destpath,unit=self.__class__.gig)):
            raise Exception("Not enough available space at: "+str(destpath)+", for image: "+str(url))
        timeout = size * time_per_gig
        self.debug('wget_image: '+str(url)+ ' to destpath'+str(destpath)+' on machine:'+str(machine.hostname))
        machine.wget_remote_image(url, path=destpath, user=user, password=password, retryconn=retryconn, timeout=timeout)
        return size
    
    def get_manifest_part_count(self, path, component=None, timeout=30):
        machine = component or self.component
        cmd = 'cat '+str(path)
        out = machine.cmd(cmd,timeout=timeout, verbose=False)
        if out['status'] != 0:
            raise Exception('get_manifest_part_count failed, cmd status:'+str(out['status']))
        output = out['output']
        tag = re.search('<parts\s+count="\d+\">', output)
        part_count = re.search("\d+",tag.group()).group()
        self.debug('get_manifest_part_count:'+str(path)+', count:'+str(part_count))
        return part_count
    
    def bundle_image(self,
                     path,
                     component=None, 
                     component_credpath=None,
                     prefix=None,
                     kernel=None,
                     ramdisk=None,
                     block_device_mapping=None,
                     destination='/disk1/storage',
                     debug=False,
                     interbundle_timeout=120, 
                     time_per_gig=None):
        '''
        Bundle an image on a 'component'. 
        where credpath to creds on component
        '''
        time_per_gig = time_per_gig or self.time_per_gig
        credpath = component_credpath or self.credpath
        machine = component or self.component
        image_size = machine.get_file_size(path)/self.gig or 1
        timeout = time_per_gig * image_size
        cbargs = [timeout, interbundle_timeout, time.time(),0, True]
        if destination is None:
            destination = machine.sys('pwd')[0]
        if (machine.get_available(str(destination),(self.gig/self.kb)) < image_size):
            raise Exception("Not enough free space at:"+str(destination))
        
        #build our tools bundle-image command...
        cmdargs = ""
        if prefix:
            cmdargs = cmdargs + " --prefix " +str(prefix)
        if kernel:
            cmdargs = cmdargs + " --kernel "  +str(kernel)
        if ramdisk:
            cmdargs = cmdargs + " --ramdisk " +str(ramdisk)
        if block_device_mapping:
            cmdargs = cmdargs + " --block-device-mapping " + str(block_device_mapping)
        if destination:
            cmdargs = cmdargs + " --destination " + str(destination)
        if debug:
            cmdargs = cmdargs + " --debug "
        
        cmdargs = cmdargs + " -i " + str(path)
        
        
        
        if credpath is not None:
            cmd = 'source '+str(credpath)+'/eucarc && euca-bundle-image ' + str(cmdargs)
        else:
            skey = self.tester.get_secret_key()
            akey = self.tester.get_access_key()
            cmd = 'euca-bundle-image -a '+str(akey) + ' -s ' + str(skey) + str(cmdargs)
        #execute the command  
        out = machine.cmd(cmd, timeout=timeout, listformat=True, cb = self.bundle_status_cb, cbargs=cbargs)
        if out['status'] != 0:
            raise Exception('bundle_image "'+str(path)+'" failed. Errcode:'+str(out['status']))
        manifest = None
        for line in out['output']:
            line = str(line)
            if re.search('Generating manifest',line):
                manifest = line.split()[2]
                break
        if manifest is None:
            raise Exception('Failed to find manifest from bundle_image:'+str(path))
        self.debug('bundle_image:'+str(path)+'. manifest:'+str(manifest))
        return manifest
    
    def upload_bundle(self, 
                      manifest, 
                      component=None, 
                      bucketname=None, 
                      component_credpath=None, 
                      debug=False, 
                      interbundle_timeout=120, 
                      timeout=0, 
                      image_check_timeout=300,
                      uniquebucket=True):
        '''
        Bundle an image on a 'component'. 
        where credpath to creds on component
        '''
        machine = component or self.component
        credpath = component_credpath or self.credpath
        cbargs = [timeout, interbundle_timeout, time.time(),0,True]
        bname = ''
        cmdargs = ""
        manifest = str(manifest)
        upmanifest = None
        part_count = -1
        try:
            part_count = self.get_manifest_part_count(manifest, component=component)
        except:
            pass
        self.debug('Attempting to upload_bundle:'+str(manifest)+", bucketname:"+str(bucketname)+", part_count:"+str(part_count))
        if bucketname:
            basename = bucketname
        else:
            #Use the image name found in the manifest as bucketname
            mlist = str(manifest.replace('.manifest.xml','')).split('/')
            basename = mlist[len(mlist)-1].replace('_','').replace('.','')
            self.debug('Using upload_bundle bucket name: '+str(basename))
        if uniquebucket:
            bx = 0 
            bname = basename+"test"+str(bx)
            while self.tester.get_bucket_by_name(bname) is not None:
                bx += 1
                bname = basename+"test"+str(bx)
        cmdargs = cmdargs + " -b " +str(basename)
        if debug:
            cmdargs = cmdargs + " --debug "
        cmdargs = cmdargs + " -b " + str(bname) + " -m " +str(manifest)

        if credpath is not None:
            cmd = 'source '+str(credpath)+'/eucarc && euca-upload-bundle ' + str(cmdargs)
        else:
            skey = self.tester.get_secret_key()
            akey = self.tester.get_access_key()
            cmd = 'euca-upload-bundle -a '+str(akey) + ' -s ' + str(skey) + str(cmdargs)
        #execute upload-bundle command...
        out = machine.cmd(cmd, timeout=image_check_timeout, listformat=True, cb=self.bundle_status_cb, cbargs=cbargs)
        if out['status'] != 0:
            raise Exception('upload_bundle "'+str(manifest)+'" failed. Errcode:'+str(out['status']))
        for line in out['output']:
            line = str(line)
            if re.search('Uploaded image',line):
                upmanifest = line.split()[3]
                break
        if upmanifest is None:
            raise Exception('Failed to find upload manifest from upload_bundle command')
        self.debug('upload_image:'+str(manifest)+'. manifest:'+str(upmanifest))
        return upmanifest
    
    
    def bundle_status_cb(self,buf, cmdtimeout, parttimeout, starttime,lasttime, check_image_stage):
        #self.debug('bundle_status_cb: cmdtimeout:'+str(cmdtimeout)+", partimeout:"+str(parttimeout)+", starttime:"+str(starttime)+", lasttime:"+str(lasttime)+", check_image_stage:"+str(check_image_stage))
        ret = SshCbReturn(stop=False)
        #if the over timeout or the callback interval has expired, then return stop=true
        #interval timeout should not be hit due to the setting of the timer value, but check here anyways
        
        if (cmdtimeout != 0) and ( int(time.time()-starttime) > cmdtimeout):
            self.debug('bundle_status_cb command timed out after '+str(cmdtimeout)+' seconds')
            ret.statuscode=-100 
            ret.stop = True
            return ret
        if not check_image_stage:
            ret.settimer = parttimeout
            if (parttimeout != 0 and lasttime != 0) and (int(time.time()-lasttime) > parttimeout):
                self.debug('bundle_status_cb inter-part time out after '+str(parttimeout)+' seconds')
                ret.statuscode=-100 
                ret.stop = True
                return ret
    
        if re.search('[P|p]art:',buf):
            sys.stdout.write("\r\x1b[K"+str(buf).strip())
            sys.stdout.flush()
            check_image_stage=False
        else: 
            #Print command output and write to ssh.cmd['output'] buffer
            ret.buf = buf
            self.debug(str(buf))
        #Command is still going, reset timer thread to intervaltimeout, provide arguments for  next time this is called from ssh cmd.
        ret.stop = False
        
        ret.nextargs =[cmdtimeout,parttimeout,starttime,time.time(),check_image_stage]
        return ret
    
    def register_image(self,
                       manifest,
                       prefix=None,
                       kernel=None,
                       ramdisk=None,
                       name=None,
                       architecture=None,
                       root_device_name=None,
                       block_device_mapping=None,
                       destination=None,
                       debug=False):
        '''convience method to register an s3 image manifest, calls eutester main method'''
        return self.tester.register_image( manifest, rdn=root_device_name, description=description, bdmdev=block_device_mapping, name=name, ramdisk=ramdisk, kernel=kernel)
    
    
    def create_emi_from_url(self, 
                            url,
                            component=None,
                            bucketname=None, 
                            component_credpath=None, 
                            debug=False, 
                            prefix=None,
                            kernel=None,
                            ramdisk=None,
                            block_device_mapping=None,
                            destination='/disk1/storage',
                            root_device_name=None,
                            description=None,
                            name=None,
                            interbundle_timeout=120, 
                            upload_timeout=0, 
                            uniquebucket=True,
                            destpath=None,
                            wget_user=None, 
                            wget_password=None, 
                            wget_retryconn=True, 
                            filepath=None,
                            bundle_manifest=None,
                            upload_manifest=None,
                            time_per_gig=300,
                            ):
        
        start = time.time() 
        self.debug('create_emi_from_url:'+str(url)+", starting...")
        if filepath is None and bundle_manifest is None and upload_manifest is None:
            filename = str(url).split('/')[-1]
            dir = destpath or self.destpath
            filepath = dir + '/' + str(filename)
            filesize = self.wget_image(url, destpath=destpath, component=component, user=wget_user, 
                                       password=wget_password, retryconn=wget_retryconn, time_per_gig=time_per_gig)
            
        self.debug('create_emi_from_url: Image downloaded to machine, now bundling image...')
        if bundle_manifest is None and upload_manifest is None:
            bundle_manifest = self.bundle_image(filepath, component=component, component_credpath=component_credpath, 
                                                prefix=prefix, kernel=kernel, ramdisk=ramdisk, block_device_mapping=block_device_mapping, 
                                                destination=destination, debug=debug, interbundle_timeout=interbundle_timeout, 
                                                time_per_gig=time_per_gig)
        
        self.debug('create_emi_from_url: Image bundled, now uploading...')
        if upload_manifest is None:
            upload_manifest = self.upload_bundle(bundle_manifest, component=component, bucketname=bucketname, 
                                                 component_credpath=component_credpath, debug=debug, interbundle_timeout=interbundle_timeout, 
                                                 timeout=upload_timeout, uniquebucket=uniquebucket)
        
        self.debug('create_emi_from_url: Now registering...')
        emi = self.tester.register_image(image_location=upload_manifest, rdn=root_device_name, 
                                         description=description, bdmdev=block_device_mapping, 
                                         name=name, ramdisk=ramdisk, kernel=kernel)
        elapsed= int(time.time()-start)
        self.debug('create_emi_from_url: Done, image registered as:'+str(emi)+", after "+str(elapsed)+" seconds")
        return emi
    