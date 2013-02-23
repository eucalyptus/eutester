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


'''
Created on Apr 13, 2012

@author: clarkmatthew

#note:
currently the test wrappers assume eucarc in the users home dir 

example:
    from eustoretests import Eustoretestsuite
    #create the eustore test suite...
    et = Eustoretestsuite(config_file="2b_tested.lst", password="foobar")
    
    #get a list of available eustore images which are not installed on the local system...
    list = et.get_uninstalled_summary()
    
    #attempt to install images from the list we just created
    #this is redundant as this will skip images found to already be installed by default
    et.install_all_images(list=list)
    
    #Attempt to run an instance and perform test suite against a list of images,
    #by default will attempt to run against all images in et.list
    et.test_image_list()
    
    #The results are redirected to logs created per image, but can be dumped to stdout using...
    #et.print_image_list_results()
    #This will print results and info for all images in et.list
    #...or print for 1 image by something like the following...
    image = et.get_eustore_image_by_string('3235725435')
    image.printdata()
    
    #this should produce something like the following...
    ------------------3235725435_CentOS_5_x86_64----------------------
    kerneltype = Single
    ver = CentOS
    name = 3235725435_CentOS_5_x86_64
    eki = eki-EB153854
    remotestring = 3235725435 centos      x86_64  2012.1.14      CentOS 5 1.3GB root, Single Kernel20120114150503      28fc-4826   centos-based           images@lists.eucalyptus.com
    id2 = 20120114150503
    rev = 5
    id3 = 28fc-4826
    email = images@lists.eucalyptus.com
    emi = emi-2B3435D5
    eri = eri-CC9432DB
    user = root,
    type = centos-based
    date = 2012.1.14
    arch = x86_64
    id = 3235725435
    distro = centos
    TEST:running_test         RESULT:SUCCESS
    TEST:terminate_test       RESULT:SUCCESS
    TEST:reboot_test          RESULT:SUCCESS
    TEST:user_test            RESULT:SUCCESS
    TEST:volume_test          RESULT:SUCCESS
    TEST:install_test         RESULT:SUCCESS
    TEST:root_test            RESULT:SUCCESS
    TEST:metadata_test        RESULT:SUCCESS
    
    



      
'''

from eucaops import Eucaops
from eutester import euinstance, euvolume
import logging
from boto.ec2.snapshot import Snapshot
from boto.ec2.image import Image
import re
import time
import unittest
import inspect
import gc
import sys
import os
#import httplib


class User():
    name = ""
    uid = ""
    group= ""
    udir = ""
    
    def __init__(self,name="",uid="",group="",udir=""):
        self.name = name
        self.id = uid
        self.group = group
        self.dir = udir
        self.__name__ = name
        self.__str__ = name
        

class TestStatus():
    not_run = "not run"
    success = "SUCCESS"
    failed = "FAILED"
    
class ImageIndex():
    '''
                id          distro      arch      date      ver      rev    size    user       kerneltype            ----           id2            id3            type          email    
           ['4150406313', 'centos', 'i386', '2011.07.02', 'CentOS', '5', '1.3GB', 'root,', 'Hypervisor-Specific', 'Kernels', '20110716161844', '6e69-7565', 'centos-based', 'images@lists.eucalyptus.com']
    '''
    id = 0   
    distro =1
    arch = 2
    date = 3
    ver = 4
    rev = 5
    size = 6
    user = 7 
    kerneltype = 8 
    #junk = 9
    id2 = 10
    id3 = 11
    type = 12
    email = 13
    
class EustoreTests():
    install_test = "install_test"
    running_test = "running_test"
    metadata_test = "metadata_test"
    user_test = "user_test"
    root_test = "root_test"
    attach_volume_test = "attach_volume_test"
    detach_volume_test = "detach_volume_test"
    reboot_test = "reboot_test"
    terminate_test = "terminate_test"
    ssh_test = "ssh_test"
    zeroconf_test = "zeroconf_test"
    virtiopresent_test = "virtiopresent_test"

class EustoreImage():
    '''
    simple class to hold data and state related to eustore images and catalog information
    '''
    
    def __init__(self, 
                id = "",
                distro = "",
                arch = "",
                date = "",
                ver = "",
                rev = "",
                size = 0,
                user = "",
                kerneltype = "", 
                id2 = "",
                id3 = "",
                type = "",
                email = "",
                emi = '', 
                eki = '',
                eri = '',
                remotestring = '',
                loginuser = 'root',
                logdir='../artifacts/'):
        
        self.id = id   
        self.distro = distro
        self.arch = arch
        self.date = date
        self.ver = ver
        self.rev = rev
        self.size = float(size)
        self.user = user
        self.kerneltype = kerneltype 
        self.id2 = id2
        self.id3 = id3
        self.type = type
        self.email = email
        self.emi = emi
        self.eki = eki
        self.eri = eri
        self.remotestring = remotestring
        self.loginuser = loginuser
        self.reservation = []
        self.name = id+"_"+ver+"_"+rev+"_"+arch  
        if not os.path.exists(logdir):
            os.makedirs(logdir)
        self.logger = logging.getLogger(self.name)
        hdlr = logging.FileHandler(logdir+self.name+".log")
        formatter = logging.Formatter('%(asctime)s:[%(funcName)s()]:[%(lineno)d]:['+str(self.name)+']: %(message)s')
        hdlr.setFormatter(formatter)
        self.logger.addHandler(hdlr)
        self.logger.setLevel(logging.DEBUG)
        #self.debug = self.logger.debug
        self.results = { 
                EustoreTests.install_test : TestStatus.not_run,
                EustoreTests.ssh_test : TestStatus.not_run,
                EustoreTests.running_test : TestStatus.not_run,
                EustoreTests.metadata_test: TestStatus.not_run,
                EustoreTests.user_test : TestStatus.not_run,
                EustoreTests.zeroconf_test : TestStatus.not_run,
                EustoreTests.root_test : TestStatus.not_run,
                EustoreTests.virtiopresent_test : TestStatus.not_run,
                EustoreTests.attach_volume_test :TestStatus.not_run,
                EustoreTests.reboot_test : TestStatus.not_run,
                EustoreTests.terminate_test :  TestStatus.not_run
               }
        self.debug("######################START#############################", verbose = False)
        
    def __str__(self):
        return self.name
 
    def debug(self, msg, verbose=True):
        if verbose:
            print msg
        self.logger.debug(msg)
    
    def printdata(self,printmethod=None):
        if printmethod is None:
            printmethod = self.debug
        printmethod("\n------------------"+str(self.name)+"----------------------")
        for key in self.__dict__:
            value = self.__dict__[key]
            if ( isinstance(value, basestring) or isinstance(value,int) ):
                printmethod( str(key)+ " = " + str(value))
        self.printresults(printmethod=printmethod)
        
    def printresults(self,printmethod = None):
        if printmethod is None:
            printmethod = self.debug
        for test in self.results:
            printmethod( str("TEST:"+str(test)).ljust(25)+str(" RESULT:"+self.results[test]).ljust(0))
            
    def clearresults(self, exclude = [EustoreTests.install_test] ):
        for test in self.results:
            for ex in exclude:
                if test == ex:
                    continue
            self.results[test]=TestStatus.not_run
            
        

class Eustoretestsuite():
    cur_image = None
    
    def __init__(self, tester=None,  config_file='../input/2b_tested.lst', password="foobar", credpath=None, url=None, list=None, volumes=None, keypair=None, group=None, image=None, zone='PARTI00',  eof=1):
        if tester is None:
            self.tester = Eucaops( config_file=config_file, password = password, credpath=credpath)
            self.tester.exit_on_fail = eof
        else:
            self.tester = tester
            self.tester.exit_on_fail = eof
        self.zone = zone
        self.url = url
        self.url_export_string = str(" ")
        if self.url is not None:
            self.url_export_string = "export EUSTORE_URL="+str(self.url)+" &> /dev/null &&"
        if list is None:
            self.list = self.get_eustore_images()
        else:
            self.list = list
            
        self.sync_installed_list()
        self.cur_image = None
        
        #Test specific resources 
        self.group = self.get_a_group()
        self.keypair = self.get_a_key()
        self.test_volumes = []
        self.test_snapshots = []
        
        
            
    def get_a_key(self):    
        '''
        helper function to get a key to use for the instance related testing
        '''
        keypair = None
        keys = self.tester.get_all_current_local_keys()
        if keys != []:
            keypair = keys[0]
        if keypair is None:
            try:
                keypair = self.tester.add_keypair("eustoretest" + "-" + str(time.time()))
            except Exception, e:
                raise Exception("Error when adding keypair. Error:"+str(e))
        return keypair
            
    def get_a_group(self, group_name="eustoregroup"):
        '''
        helper function to fetch a group to use for the instance related testing
        '''
        try:
            group = self.tester.add_group(group_name)
            self.tester.authorize_group_by_name(group.name)
            self.tester.authorize_group_by_name(group.name,protocol="icmp",port=-1)
        except Exception, e:    
            raise Exception("Error when setting up group:"+str(group_name)+", Error:"+str(e))
        return group
              
    def debug(self,msg):
        if self.cur_image is not None:
            self.cur_image.debug(msg)
        return self.tester.debug(msg)
    
    
    def create_image_from_emi(self,emi,name=None, id=None, size=2, add=True):
        '''
        Method used to build a eustore image object from an existing EMI. Mainly used to create an object that 
        can be fed into the test suite. By default this will append the image to this Eustoretestsuite image list
        Returns a eustore image object
        emi - mandatory - emi image object
        name -optional- name used in eustore object to be created
        id -optional- id used in eustore object to be created
        size -optional- size used in eustore object to be created
        add -optional- boolean- add to local eustore list of this eustoretestsuite
        '''
        newimg = EustoreImage()
        if id is None:
            newimg.id = emi.id
        else:
            newimg.id = id
            
        if name is None:
            newimg.name = emi.location
        else:
            newimg.name = name
            
        newimg.eki = emi.kernel_id
        newimg.eri = emi.ramdisk_id
        newimg.emi = emi.id
        newimg.size = size
        if add:
            self.list.append(newimg)
        return newimg

        
    def convert_image_list_to_eustore_images(self,list, prefix="", size=2, add=True):
        '''
        Method to convert list of non-eustore system images to eustore images. Returns list of the converted eustore images
        list - mandatory - list of images to convert
        prefix - a string prefixed to the stored image name
        id - a string to be used as the image's id, otherwise will use the underlying image's location string
        size - expected size of the image, used for determining the appropriate minimum instance type when running
        add - boolean, used to determine if this eustore image should be added to the main eustore image list
        '''
        retlist = []
        for image in list:
            name = str(prefix)+"-"+str(image.location)
            retlist.append(self.create_image_from_emi(image, name=name, id=image.location, size=size, add=add))
        return retlist
        
        
    
    def get_eustore_images(self):
        '''
        Attempts to populate a list of images by retrieving image attributes from eustore command(s).   
        '''
        ii = ImageIndex()
        images = []
        out = self.tester.sys( self.url_export_string+" eustore-describe-images -v")
        l = 0
        while (l < len(out)):
            line = out[l].strip().split()+out[l+1].strip().split()
            image = EustoreImage(
                                id = line[ii.id],
                                distro = line[ii.distro],
                                arch = line[ii.arch],
                                date = line[ii.date],
                                ver = line[ii.ver],
                                rev = line[ii.rev],
                                size = float(re.sub("GB","", line[ii.size])),
                                user = line[ii.user],
                                kerneltype = line[ii.kerneltype], 
                                id2 = line[ii.id2],
                                id3 = line[ii.id3],
                                type = line[ii.type],
                                email = line[ii.email],
                                remotestring = out[l].strip()+out[l+1].strip(),
                                )
            image.loginuser = self.get_default_login_user_by_distro(ii.distro)
            
            images.append(image)
            l += 2
        return images
            
    def get_default_login_user_by_distro(self,distro):
        '''
        helper method to return default login user per distro
        '''
        if re.search('UBUNTU', str(distro).upper()):
            return 'ubuntu'
        else:
            return 'root'
            
    def get_system_images(self, emi=None, root_device_type=None, root_device_name=None, location=None, state="available", arch=None, owner_id=None):
        """
        Get images matching the provided criteria. 
        By default matches image location containing the  string held by the 'location' option.
        emi              (optional string ) Partial ID of the emi to return, ie to grab all EMI use emi="emi-"prefix to grab any
        root_device_type (optional string)  example: 'instance-store' or 'ebs'
        root_device_name (optional string)  example: '/dev/sdb' 
        location         (optional string)  partial on location match example: 'centos'
        state            (optional string)  example: 'available'
        arch             (optional string)  example: 'x86_64'
        owner_id         (optional string) owners numeric id
        """
        retlist = []    
        images = self.tester.ec2.get_all_images()
        for image in images:
            
            if (emi is not None) and (not re.search(emi, image.id)):      
                continue  
            if ((root_device_type is not None) and (image.root_device_type != root_device_type)):
                continue            
            if ((root_device_name is not None) and (image.root_device_name != root_device_name)):
                continue       
            if ((state is not None) and (image.state != state)):
                continue            
            if ((location is not None) and (not re.search( location, image.location))):
                continue           
            if ((arch is not None) and (image.architecture != arch)):
                continue                
            if ((owner_id is not None) and (image.owner_id != owner_id)):
                continue
            
            retlist.append(image)
        return retlist
            
            
            
    def get_registered_emis(self, eustore_image,  emi="emi-"):
        '''
        Attempts to return a list of emis using this eustore image
        eustore_image - mandatory - eustore image object
        emi - optional - string used to filter matched images 
        '''
        images = self.get_system_images(emi, location=eustore_image.id)    
        if images == []:
            return None
        else:
            return images
    
    def get_registered_ekis(self, eustore_image):
        '''
        Attempts to get a list of ekis using this eustore image
        eustore_image - mandatory - eustore image object
        '''
        return self.get_registered_emis(eustore_image, emi="eki-")
    
    def get_registered_eris(self, eustore_image):
        '''
        Attempts to get a list of eris using this eustore image
        eustore_image - mandatory - eustore image object
        '''
        return self.get_registered_emis(eustore_image, emi="eri-")
    
        
   
            
    def install_image(self,eustore_image,
                      help=False,
                      tarball=None,
                      description=None,
                      arch=None,
                      prefix=None,
                      bucket=None,
                      kernel_type=None,
                      dir="/disk1/storage",
                      kernel=None,
                      ramdisk=None,
                      url=None,
                      region=None,
                      access_key=None,
                      secret_key=None,
                      force=False, 
                      eucarc=False,
                      rcpath="eucarc",
                      xof=False,
                      timepergig=1000):
        '''
        Attempts to install and verify an image using the eustore-install command. Creates the command with all the available arguments, and then verifies that
        the appropriate images were installed and registered correctly. 
        help - optional - Boolean - issue eustore command with help flag
        tarball - optional - String - specify local tarball path in which to install from
        description - optional - String - provide description arg to eustore command
        arch= - optional - String provide arch type of image i386 or x86_64
        prefix - optional - String -prefix to use when naming the image, mostly used with tarball option
        bucket= - optional - String - bucket name
        kernel_type -optional -String representing xen or kvm kernel type
        dir - optional -String local directory to unbundle image
        kernel - optional - String eki of installed kernel image to use instead
        ramdisk - optional - string eri of installed ramdisk image to use instead
        url - optional - overide url with this option
        region - optional - String, Name of the region to connect to
        access_key - optional - String, Override access key value
        secret_key - optional - String, Override secret key value
        force - optional - boolean, force installation if image is detected as already installed
        eucarc - optional - boolean, to source eucarc at rc_path
        xof - optional - boolean, to exit on fail
        timepergig - optional - time expected per gig used to determine timeouts
        '''
        image = eustore_image
        self.cur_image = image
        cmd = ""
        start = time.time()
        
        #Check to see if image has already been installed
        if (not force) and  (self.get_registered_emis(eustore_image) is not None):
            eustore_image.results[EustoreTests.install_test] = TestStatus.success
            raise Exception('Image:"'+str(image.name)+'" is already installed')
       
        timeout = int(image.size*timepergig)
        print "image.size:"+str(image.size)+" and timepergig:"+str(timepergig)+" = timeout:"+str(timeout)
        
        #Build the eustore command...
        if eucarc:
            cmd = "source "+str(rcpath)+" && "
        cmd = cmd + self.url_export_string+" eustore-install-image"+self.get_standard_opts(url=url, region=region, access_key=access_key, secret_key=secret_key)  
        cmd = cmd + " -i "+str(eustore_image.id)
        if help == True:
            cmd = cmd + " -h"
            
        if tarball is not None:
            cmd = cmd + " -t "+ str(tarball)
            
        if description is not None:
            cmd = cmd + " -s "+ str(description)
            
        if arch is not None:
            cmd = cmd + " -a "+ str(arch)
            
        if prefix is not None:
            cmd = cmd + " -p "+ str(prefix)
            
        if kernel_type is not None:
            cmd = cmd + " -k "+ str(kernel_type)
        else:
            kernel_type = ""
            
        if bucket is not None:
            cmd = cmd + " -b "+ str(bucket)
        else:
            cmd = cmd + " -b "+ str(eustore_image.name).lower()+"_"+str(kernel_type)
            
        if dir is not None:
            cmd = cmd + " -d "+ str(dir)
            
        if kernel is not None:
            cmd = cmd + " --kernel="+str(kernel)
            
        if ramdisk is not None:
            cmd = cmd + " --ramdisk="+str(ramdisk)
        
        cmd = cmd + " && echo 'SUCCESS'"
        print "-----------------------------------------------------------------------------------------"
        print "-----------------------------------------------------------------------------------------"
        print " image: "+image.name+"_"+str(kernel_type)
        print "-----------------------------------------------------------------------------------------"
        print "-----------------------------------------------------------------------------------------"
        print "Executing cmd:"+str(cmd)
        try:     
            out = self.tester.sys(cmd, timeout=timeout)
            if re.search("SUCCESS",out[len(out)-1]):
                for line in out:
                    if re.search("Error", line):
                        self.debug("Found Error from cmd:"+str(cmd))
                        raise Exception("Found Error from cmd:"+str(cmd))
            else:
                self.debug("Command exited with err:"+str(cmd))
                raise Exception("Command exited with err:"+str(cmd))
            
            
            #Now verify the appropriate images were actually installed on the system
            emi = self.get_registered_emis(eustore_image)[0]
            if (emi is None):
                self.debug('Image:"'+str(image.name)+'" is not found on system after install')
                raise Exception('Image:"'+str(image.name)+'" is not found on system after install')
            
            #Get the associated eki and eri
            eki_id = emi.kernel_id
            eri_id = emi.ramdisk_id
            
            #Verify the appropriate EKI was installed and associated with this EMI
            if (kernel is not None): 
                if(kernel != eki_id):
                    self.debug("Kernel specified does not match specified EKI. EMI:"+str(emi.id)+" Image:"+str(image.name))
                    raise Exception("Kernel specified does not match specified EKI. EMI:"+str(emi.id)+" Image:"+str(image.name)) 
            else:
                eki = self.get_registered_ekis(eustore_image)[0]
                if eki is None:
                    self.debug('EKI for Image:"'+str(image.name)+'" is not found on system after install')
                    raise Exception('EKI for Image:"'+str(image.name)+'" is not found on system after install')
                else:
                    if (eki.id != eki_id):
                        self.debug("Kernel specified does not match associated EKI. EMI:"+str(emi.id)+" Image:"+str(image.name))
                        raise Exception("Kernel specified does not match associated EKI. EMI:"+str(emi.id)+" Image:"+str(image.name))
            self.debug( "Image:"+str(image.name)+" installed kernel:"+str(eki_id))
            #Verify the appropriate ERI was installed and associated with this EMI        
            if (ramdisk is not None):
                if (ramdisk != eri_id):
                    self.debug("Ramdisk specified does not match associated ERI. EMI:"+str(emi.id)+" Image:"+str(image.name))
                    raise Exception("Ramdisk specified does not match associated ERI. EMI:"+str(emi.id)+" Image:"+str(image.name))
            else:
                eri = self.get_registered_eris(eustore_image)[0]
                if eri is None:
                    self.debug('ERI for Image:"'+str(image.name)+'" is not found on system after install')
                    raise Exception('ERI for Image:"'+str(image.name)+'" is not found on system after install')
                else:
                    if (eri.id != eri_id):
                        self.debug("Ramdisk specified does not match associated ERI. EMI:"+str(emi.id)+" Image:"+str(image.name))
                        raise Exception("Ramdisk specified does not match associated ERI. EMI:"+str(emi.id)+" Image:"+str(image.name))
            image.emi = emi.id
            image.eri = eri_id
            image.eki = eki_id
            
            eustore_image.results[EustoreTests.install_test] = TestStatus.success
            self.debug(cmd+" Succeeded")  
        except Exception, e:
            eustore_image.results[EustoreTests.install_test] = TestStatus.failed
            self.debug("Image:"+image.name+" failed to install, err:"+str(e))
            if xof:
                raise Exception("Image:"+image.name+" failed to install, err:"+str(e))
        
        finally:
            elapsed = int(time.time()-start)
            self.debug("Command finish in: "+str(elapsed)+" seconds")
            self.cur_image = None
        
    
            
    def get_standard_opts(self,url=None,region=None,access_key=None,secret_key=None):    
        '''
        Helper method to create the standard options string(s) used when executing a command without sourcing
        eucarc
        '''
        ret = ""
        if region is not None:
            ret = ret+"--region="+str(region)+" "  
        if access_key is not None:
            ret = ret+"-I "+str(access_key)+" "
        if secret_key is not None:   
            ret = ret+"-S "+str(secret_key)+" "
        return ret
        
    
    def get_eustore_image_by_string(self, searchstring, list=None, searchall=False):
        '''
        Attempts to return a list of eustore images by matching the given string to any string in the eustore describe images output
        This output is stored in the eustoreimage.remotestring. 
        '''

        retlist = []
        if list is None:
            list = self.list
        for image in list: 
            if searchall:
                if re.search(searchstring, it.tester.get_all_attributes(image, verbose=False)):
                    retlist.append(image)
            if re.search(searchstring, image.remotestring) or re.search(searchstring,image.id):
                retlist.append(image)
        return retlist
        
    
    def install_all_images(self, hyper="both",eucarc=True, searchstring=None, imglist = None, force=False):
        '''
        Attempts to install all images either in self.list or the provided imglist. 
        By default will install both xen and kvm images, but this can be limited by use of the hyper var.
        Options:
        hyper -optional string - kvm, xen, both. Used to determine which image to use for installation
        eucarc - optional- used to determine whether or not the command should source the eucarc or specify args instead
        searchstring - optional-  will only install images whos remote string matches the given string
        imglist -optional - defaults to self.list, list used to gather all images to be installed
        force - optional - if True, will attempt to install if existing image is detected. Otherwise will skip installed images.
        '''
        if imglist is None:
            imglist = self.list
        if searchstring is not None:
            imglist = self.get_eustore_image_by_string(searchstring, list=imglist)
        for image in imglist:
            try: 
                if (image.kerneltype == "Single"):
                    self.debug("Installing image:"+image.name+" kernel_type:"+image.kerneltype+" , HYPER:NONE")
                    self.install_image(image, eucarc=eucarc)
                else:
                    if (hyper == "both" ) or (hyper == "xen"):
                        self.debug("Installing image:"+image.name+" kernel_type:"+image.kerneltype+" HYPER:XEN")
                        self.install_image(image, eucarc=True, kernel_type="xen")
                    if (hyper == "both ") or (hyper == "kvm"):
                        self.debug("Installing image:"+image.name+" kernel_type:"+image.kerneltype+" HYPER:KVM")
                        self.install_image(image, eucarc=True, kernel_type="kvm")      
            except Exception, ie:
                self.debug("Image;"+image.name+" failed."+str(ie))
                pass
    
    def get_eustore_image_by_id(self, emi_id=None, eri_id=None, eki_id=None):
        '''
        Returns a list of eustore images which match the provided emi,eri,eki ids of the installed images
        '''
        
        
        for image in self.list:
            if (emi_id is not None) and (not re.search(emi_id, image.emi)):      
                continue  
            if (eki_id is not None) and (not re.search(eki_id, image.eki)):      
                continue
            if (eri_id is not None) and (not re.search(eri_id, image.eri)):      
                continue
            self.debug("get_eustore_image_by_id,emi_id="+str(emi_id)+" = "+str(image.name))
            return image
        return None
        
        
        
    def sync_installed_list(self, updateimage=True):
        '''
        Attempts to get a diff of images in our list vs what the system is reporting. 
        This relies upon the bucket location having the image id text in it. 
        Returns a list of images found in our eustore list that are not believed 
        to be installed on the system. Can be later passed to install_all_images, etc..
        '''
        retlist = []
        for image in self.list:
            self.debug("Checking to see if image:"+str(image.name)+" is installed")
            emis = self.get_registered_emis(image)
            if emis is None:
                self.debug("Image: "+str(image.name)+" not found on system")
                retlist.append(image)
            else:
                emi = emis[0]
                self.debug("Image: "+str(image.name)+" found installed on system")
                if updateimage:
                    #Get the associated eki and eri
                    image.eki = emi.kernel_id
                    image.eri = emi.ramdisk_id
                    image.emi = emi.id
                    image.results[EustoreTests.install_test]=TestStatus.success
        return retlist
    
    def print_image_list(self,list=None, verbose=False):
        '''
        Traverses a list of images and displays the image information and current test results status.
        '''
        if list is None:
            list = self.list
        for image in list:
            self.debug("IMAGE: "+str(image.name)+" Install Status: "+str(image.results[EustoreTests.install_test]))
            if verbose:
                image.printdata()
                    
    def test_image_list(self, image_list=None, vmtype= None, zone=None, userlist=[], rootpass=None, xof=False,volcount=2):
        '''
        Attempts to traverse a list of images and run the image test suite against them
        '''
        if image_list is None:
            image_list = self.list
        if zone is None:
            zone = self.zone    
        for image in image_list:
            try:
                self.run_image_test_suite(image, vmtype=None, zone=zone, userlist=[], rootpass=None, xof=False,volcount=2)
                time.sleep(10)
            except Exception, e:
                self.debug("Caught Exception while running image test for:"+str(image.name)+", err:"+str(e))
                pass
            

            
                
                
    def run_image_test_suite(self,image, vmtype=None, zone='PARTI00', userlist=[], rootpass=None, xof=False, volcount=2):  
        '''
        Runs a set of tests against an image, starts by running an euinstance of an image. If the image continues
        to running the remaining tests are ran against the image. Logging/results/debugging messages should be printed to the
        image specific dir/file. usually ../artifacts/*imagename*.log
        
        '''
        self.cur_image = image #set logger for this image    
        image.clearresults()
        failcode = 0 
        
        try:
            #first try to run the image, exit if this fails as there's no point in running the remaining tests
            try:
                res = self.run_image(image, vmtype=vmtype, zone=zone)
                inst = res.instances[0]
            except Exception, re:
                image.results[EustoreTests.running_test] = TestStatus.failed
                self.debug("("+str(image.name)+") error:"+str(re))
                raise re
                return
            
            try:
                self.instance_ssh_test(inst, image=image)
                self.debug("SUCCESS - SSH TEST - ("+str(image.name)+")")
            except Exception, e:
                self.debug("!!!!!! FAILED - SSH TEST - ("+str(image.name)+") error:"+str(e))
                failcode = 1 
                raise e
                return
            
            #Perform tests on the running instance, continue on failure for these tests
            try:
                self.instance_metadata_test(inst, image=image)
                self.debug("SUCCESS - METADATA TEST - ("+str(image.name)+")")
            except Exception, e:
                self.debug("!!!!!! FAILED - METADATA TEST - ("+str(image.name)+") error:"+str(e))
                failcode = 1 
                pass
            
            try:
                self.instance_root_test(inst, image=image)
                self.debug("SUCCESS - ROOT TEST - ("+str(image.name)+")")
            except Exception, e:
                self.debug("!!!!!! FAILED - ROOT TEST - ("+str(image.name)+") error:"+str(e))
                failcode = 1 
                pass
            
            try:
                self.instance_users_test(inst, userlist=userlist, image=image)
                self.debug("SUCCESS - USERS TEST - ("+str(image.name)+")")
            except Exception, e:
                self.debug("!!!!!! FAILED - USERS TEST - ("+str(image.name)+") error:"+str(e))
                failcode = 1 
                pass
            
            try:
                self.instance_zeroconf_test(inst, image=image)
                self.debug("SUCCESS - ZEROCONF TEST - ("+str(image.name)+")")
            except Exception, e:
                self.debug("!!!!!! FAILED - ZEROCONF TEST - ("+str(image.name)+") error:"+str(e))
                failcode = 1 
                pass
            
            try:
                self.instance_virtio_present_test(inst, image=image)
                self.debug("SUCCESS - VIRTIO PRESENT TEST - ("+str(image.name)+")")
            except Exception, e:
                self.debug("!!!!!! FAILED - VIRTIO PRESENT TEST - ("+str(image.name)+") error:"+str(e))
                failcode = 1 
                pass
            
            try:    
                self.instance_attach_vol_test(inst,volcount=volcount, image=image)
                self.debug("SUCCESS - ATTACH VOLUMES TEST - ("+str(image.name)+")")
            except Exception, e:
                self.debug("!!!!!! FAILED - ATTACH VOLUME TEST - ("+str(image.name)+") error:"+str(e))
                failcode = 1 
                pass
            
            try:
                self.instance_reboot_test(inst, image=image)
                self.debug("SUCCESS - REBOOT TEST - ("+str(image.name)+")")
            except Exception, e:
                self.debug("!!!!!! FAILED - REBOOT TEST - ("+str(image.name)+") error:"+str(e))
                failcode = 1 
                pass
            
            try:
                self.instance_detach_volumes_test(inst, count=volcount, image=image)
                self.debug("SUCCESS - DETACH VOLUMES TEST - ("+str(image.name)+")")
            except Exception, e:
                self.debug("!!!!!! FAILED - DETACH VOLUMES TEST - ("+str(image.name)+") error:"+str(e))
                failcode = 1 
                pass
                
            try:
                self.instance_terminate_test(res, image=image)
                self.debug("SUCCESS - TERMINATE TEST - ("+str(image.name)+")")
            except Exception, e: 
                self.debug("!!!!!! FAILED -  TEST - ("+str(image.name)+") error:"+str(e))
                failcode = 1 
                pass
            
            
        except Exception, e:
            self.debug("!!!!!! FAILED  - ("+str(image.name)+") error:"+str(e))
            failcode = 1
            raise e
        finally:
            self.clean_up_running_instances_for_image(image)
            
            self.debug(str('FAIL' if failcode == 1 else "SUCCESS")+" IMAGE:"+str(image.name))
            image.printdata(printmethod=self.debug)
            self.cur_image = None
            return failcode
        
            
    def clean_up_running_instances_for_image(self,image, timeout=300):
        '''
        Additional cleanup mechanism to help remove instances from failed terminate tests
        image - optional - eustoreimage object to report results against
        timeout - optional - seconds to wait on cleanup before failure
        
        '''
        self.debug("clean_up_running_instance_for_image: "+str(image.name))
        failstr=''
        emis = self.get_registered_emis(image)
        if emis != []:
            emi = emis[0]
            for instance in self.tester.get_instances(image_id=emi.id):
                try:
                    if (instance.state != 'terminated'):
                        self.debug("Found Instance to terminate:"+str(instance.id))
                        instance.terminate()
                        self.tester.wait_for_instance(instance, state='terminated')
                    self.debug("Instance:"+str(instance.id)+" terminated")
                except Exception, e:
                    failstr = failstr+ "instance:"+instance.id+"Failed:"+str(e)+"\n"
                    pass
        else:
            self.debug("No instances found to clean up")
        if failstr != '':
            raise Exception("Failed to terminated instances:"+str(failstr))
        
                
            
    def run_image(self,image, username=None, password=None, vmtype=None, zone='PARTI00'):
        '''
        Attempts to verify that an instance from the provided image can be ran, by
        default an ssh session will be created to this sesssion. If the instance does not progress
        to running state within a given timeout, or if the ssh connection can not be established, the 
        test will fail. 
        inst - mandatory - euinstance object
        username - optional- username to use for ssh login for this instance
        password - optional - password to user for ssh login for this instance (key'd login by default)
        vmtype - optional - string representing vmtype, otherwise test will attempt to determine vmtype based on eustoreimage size
        zone - optional - string representing availability zone to launch image in
        image - optional - eustoreimage object to report results against
        '''
        
        if vmtype is None:
            if image.size <= 2:
                vmtype = 'c1.medium'
            elif image.size <= 5:
                vmtype = 'm1.large'
            else:
                vmtype = 'm1.xlarge'
        self.debug("#####STARTING run_image test########")
        image.results[EustoreTests.running_test] = TestStatus.failed
        if username is None:
            username = str(image.loginuser)
        try:
            emi = self.get_registered_emis(image)[0]
        except Exception, e:
            raise Exception("Could not get registered EMI for image:"+str(image)+" err:"+str(e))
        
        self.debug("Running image:"+str(image)+", vmtype:"+str(vmtype)+" keypair:"+str(self.keypair.name)+" group:"+str(self.group)+" zone:"+str(zone))
        res = self.tester.run_instance(image=emi, keypair=self.keypair.name, group=self.group, type=vmtype, zone=zone,username=username, password=password)
        if res == []:          
            raise Exception("Reservation was empty, failed to run: "+str(image))      
        image.results[EustoreTests.running_test] = TestStatus.success
        return res
        
        
    def instance_ssh_test(self,inst,image=None):
        '''
        This test attempts to issue a remote command via the euinstance ssh session and
        verify the  output
        inst - mandatory - euinstance object
        image - optional - eustoreimage object to report results against
        '''
        self.debug("################STARTING instance_ssh_test #####################")
        if image is None:
            image = self.get_eustore_image_by_id(emi_id=inst.image_id)
        self.set_result(image,EustoreTests.ssh_test, TestStatus.failed )
        try:
            if inst.found("echo 'good'", "^good"):
               self.set_result(image,EustoreTests.ssh_test, TestStatus.success)
               return
            else:
                raise Exception("Expected text not returned from remote ssh command")
        except Exception, e:
            raise Exception("("+str(image)+") Failed ssh command test:"+str(inst.id)+"err:"+str(e))
            
        
            
    def instance_metadata_test(self,inst,image=None):
        '''
        This test attempts to verify the basic functionality of Metadata
        on this instance
        inst - mandatory - euinstance object
        image - optional - eustoreimage object to report results against
        '''
        self.debug("#######STARTING instance_metadata_test##########")
        if image is None:
            image = self.get_eustore_image_by_id(emi_id=inst.image_id)
        self.set_result(image, EustoreTests.metadata_test, TestStatus.failed)
       
        if inst.get_metadata('instance-id')[0] != inst.id:
            raise Exception("("+str(image)+") Metadata test failed")
        self.set_result(image, EustoreTests.metadata_test, TestStatus.success)
        
        
    def instance_virtio_present_test(self,inst,image=None):
        '''
        This test attempts to verify that the instance has the virtio kernel modules available. 
        It does not check if they are installed per NC configuration. 
        inst - mandatory - euinstance object
        image - optional - eustoreimage object to report results against
        '''
        self.debug("#######STARTING instance_virtio_present_test##########")
        if image is None:
            image = self.get_eustore_image_by_id(emi_id=inst.image_id)
        self.set_result(image, EustoreTests.virtiopresent_test, TestStatus.failed)
        #look for filename line in modinfo...
        #filename:       /lib/modules/2.6.28-11-generic/kernel/drivers/virtio/virtio.ko
        out = inst.sys('modinfo virtio')
        for line in out:
            if (re.search("^filename", line) and re.search("virtio.ko", line)):
                self.set_result(image, EustoreTests.virtiopresent_test, TestStatus.success) 
                return          
        raise Exception("("+str(image)+") virtio present test failed")
               
   
        
    def instance_attach_vol_test(self,inst, volcount=1, recycle=True, image=None, vol_list=[], timepergig=180):
        '''
        This test attempt to verify attachment of volume(s) to an instance
        inst - mandatory - euinstance object
        volcount - optional - number of volumes to attach to instance if a vol_list is not provided
        recycle - boolean - first attempt to use existing volumes for this test rather create new ones
        image - optional - eustoreimage object to report results against
        vol_list -optional -list of euvolumes to be attached to instance
        '''

        self.debug("###########STARTING instance_attach_vol_test##########")
        vols = 0
        if image is None:
            image = self.get_eustore_image_by_id(emi_id=inst.image_id)
        self.set_result(image, EustoreTests.attach_volume_test, TestStatus.failed)
    
        zone = inst.placement
        try:
            if vol_list != []:
                for vol in vol_list and vols <= volcount:
                    inst.attach_volume(vol)
                    vols += 1 
            else:
                for i in xrange(0,volcount):
                    if recycle:
                        try:
                            vol = self.tester.get_volume(status='available', zone=zone, maxsize=1)
                            self.debug('Using recycled and available:'+str(vol))
                        except Exception, e:
                            self.debug("Err trying to get an existing volume, making new one... err:"+str(e))
                            vol = self.tester.create_volume(zone, timepergig=timepergig)
                            pass
                    else:
                        elf.debug("Recycle vols not set, created new")      
                        vol = self.tester.create_volume(zone)              
                    timeout= vol.size * timepergig
                    inst.attach_volume(vol,timeout=timeout)
        except Exception, ae:
            raise Exception("("+str(image)+") Failed to attach volume to:"+str(inst.id)+"err:"+str(ae))
        self.set_result(image, EustoreTests.attach_volume_test, TestStatus.success)
        
    
    def instance_detach_volumes_test(self, inst, image=None, count=0, timeout=60):
        '''
        Attempts to verify 'count' number of volumes detach correctly from an instance
        inst - mandatory - euinstance object
        image - optional - eustoreimage object to report results against
        count - optional - integer, # of volumes to detach from instance. 0 = all
        timeout - optional - integer. # of seconds to wait for volumes to detach before failure
        '''
        self.debug("#############STARTING instance_detach_volume_test#############")
       
        attached_count = len(inst.attached_vols)
        if attached_count == 0:
            self.debug("("+str(image)+")No attached volumes detected, skipping detach volume test:"+str(inst.id))
            self.set_result(image, EustoreTests.detach_volume_test, TestStatus.not_run)
            return
        if count == 0:
            count = attached_count
        if image is None:
            image = self.get_eustore_image_by_id(emi_id=inst.image_id)
        self.set_result(image, EustoreTests.detach_volume_test, TestStatus.failed)
       
        try:
            detached = 0
            for evol in inst.attached_vols:
                inst.detach_euvolume(evol, timeout=timeout)
                detached += 1
                if detached >= count:
                    break
        except Exception, e:
            raise Exception("("+str(image)+") Failed to detattach volumes:"+str(inst.id)+"err:"+str(e))
        self.set_result(image, EustoreTests.detach_volume_test, TestStatus.success)
        
    
    def instance_reboot_test(self,inst, checkvolstatus=True, image=None):
        '''
        This attempt to reboot an instance, if volumes were present before the reboot, this test
        will attempt to verify that those volumes are intact as well as verify data integrity with md5
        inst - mandatory - euinstance object
        image - optional - eustoreimage object to report results against
        checkvolstatus - boolean - flag to confirm volume attached states post reboot
        
        '''
        
        self.debug("############STARTING instance_reboot_test#############")
        if image is None:
            image = self.get_eustore_image_by_id(emi_id=inst.image_id)
        self.set_result(image, EustoreTests.reboot_test, TestStatus.failed)
        
        try:
            inst.reboot_instance_and_verify(checkvolstatus=checkvolstatus)
            self.set_result(image, EustoreTests.reboot_test, TestStatus.success)
            return
        except Exception, e:
            self.set_result(image, EustoreTests.reboot_test, TestStatus.failed)
            raise Exception("("+str(image)+")Failed instance_reboot_test, err:"+str(e))
        
        
    def instance_users_test(self, inst, userlist=[], image=None):
        '''
        This attempts to verify that no nomral (non-system) users are present on 
        the instance/image.
        inst - mandatory - euinstance object
        userlist - optional - list strings representing user names  expected to be found on instance. 
        image - optional - eustoreimage object to report results against
        
        '''
        self.debug("############STARTING instance_users_test#################")
        if image is None:
            image = self.get_eustore_image_by_id(emi_id=inst.image_id)
        self.set_result(image, EustoreTests.user_test, TestStatus.failed)
       
        users = inst.get_users() 
        if users != userlist:
            raise Exception("("+str(image)+")Image has unknown Non-system users: "+"".join(users))
        self.set_result(image, EustoreTests.user_test, TestStatus.success)
        
        
        
    def instance_zeroconf_test(self, inst, netfile='/etc/sysconfig/network', image=None):
        '''
        This test attempts to verify the instance is not using zeroconf network configuration. 
        The zeroconf config may conflict with certain network modes.
        Note: netfile set to null only checks routing table for 169.254.0.0 addr
        inst - mandatory - euinstance object
        netfile - optional -string representing file path to network config
        image - optional - eustoreimage object to report results against
        '''
        self.debug("############STARTING instance_zeroconf_test#################")
        if image is None:
            image = self.get_eustore_image_by_id(emi_id=inst.image_id)
        self.set_result(image, EustoreTests.zeroconf_test, TestStatus.failed)
            
        if netfile is not None:
            #First verify netfile exists
            try:
                out = inst.sys("ls "+str(netfile))[0].strip()
                if ( out != netfile ):
                    raise Exception(str(out) +"!=" +  str(netfile))
            except Exception, e:
                raise Exception("Could not stat:"+str(netfile)+", err:"+str(e))
            
            #Verify the network file has zeroconf disabled
            cmd = "cat "+str(netfile)+" | grep NOZEROCONF | grep -v '^#'"         
            if inst.found(cmd,"NOZEROCONF"):
                self.debug("Found NOZEROCONF in:"+str(netfile))
            else:
                raise Exception("NOZEROCONF not found, zero conf is not disabled")
        
        if inst.found('route -n', '169.254.0.0'):
            raise Exception("ZEROCONF network detected in instance")
        self.set_result(image, EustoreTests.zeroconf_test, TestStatus.success)
        

        
    def instance_root_test(self, inst, password = None, image=None):
        '''
        Attempts to verify whether the root user on the instance has a password or not. 
        A password can be specififed if it is expected, by default it expects no password
        inst - mandatory - euinstance object
        password - optional - string representing an expected root user password
        image - optional - eustoreimage object to report results against
        '''
        self.debug("############STARTING isntance_root_test################")
        if image is None:
            image = self.get_eustore_image_by_id(emi_id=inst.image_id)
        self.set_result(image, EustoreTests.root_test, TestStatus.failed)
        ipassword = inst.get_user_password('root') 
        if ipassword != password:
            self.set_result(image, EustoreTests.root_test, TestStatus.failed)
            raise Exception("("+str(image)+")root user has bad password! found:"+str(ipassword)+"!="+str(password))
        self.set_result(image, EustoreTests.root_test, TestStatus.success)
       
        
        
 
        
    def instance_terminate_test(self,res,image=None):
        '''
        Attempts to confirm that an image terminates within a certain timeout
        res - mandatory - reservation of instance(s) to terminate
        image - optional - eustoreimage object to report results against
        '''
        self.debug("#######STARTING instance_terminate_test##########")
        if res.instances == []:
            self.debug('Reservation was empty in instance_terminate_test. Not running')
            self.set_result(image, EustoreTests.terminate_test, TestStatus.not_run)
            return
        try:
            if image is None:
                inst = res.instances[0]
                image = self.get_eustore_image_by_id(emi_id=inst.image_id)
            self.set_result(image, EustoreTests.terminate_test, TestStatus.failed)
            self.tester.terminate_instances(res)
            self.set_result(image, EustoreTests.terminate_test, TestStatus.success)
        except Exception, e:
            self.debug("Trying single Termination, Problem with terminating reservation:" +str(e))
            try:
                self.clean_up_running_instances_for_image(image)
                self.set_result(image, EustoreTests.terminate_test, TestStatus.success)
                return
            except Exception, se:
                self.debug("Failed single termination for image:"+str(image))
                raise se
                

    def get_images_by_test_result(self,list=None, eustoretest=None,result=TestStatus.failed ):
        """ 
        Attempts to return a subset list of images who's test results match the result give. 
        By default this will traverse each image in self.list, will then traverse the image.results list for each
        EustoreTest matching TestStatus.failed.
        list - optional - list of eustoreimages to search within
        eustoretest - optional - eustore test used in search criteria
        result - optional - TestStatus type result to search for
        """
        retlist = []
        if list is None:
            list = self.list
        
        if eustoretest is None:
            #return all images who have any test which results matches 'result'
            for image in list:
                for test in image.results:
                    if image.results[test] == result:
                        retlist.append(image)
            return retlist
        else:
            #return any images whos specific eustore test mataches 'result'
            for image in list:
                try:
                    t = EustoreTests.__dict__[eustoretest]
                except Exception, te:
                    raise Exception("get_images_by_test_result, provided invalid test type:"+str(eustoretest)+", err;"+str(te))
                if image.results[t] == result:
                    retlist.append(image)
            return retlist
        
    
    
        
    def set_result(self,image,test,status):
        '''
        convience method to apply test results to an image
        '''
        #if image is none do nothing
        if image is None:
            return
        self.validate_eustore_test(test)
        self.validate_eustore_status(status)
        image.results[test] = status
        
    def validate_eustore_test(self,test):
        '''
        Validate a given test is defined as a eustore test
        '''
        for k in EustoreTests.__dict__:
            if test == EustoreTests.__dict__[k]:
                return 
        raise Exception("Test '"+str(test)+"' is  not defined in EustoreTests")
    
    def validate_eustore_status(self, status):
        '''
        Validate a given status is defined
        '''
        for k in TestStatus.__dict__:
            if status == TestStatus.__dict__[k]:
                return 
        raise Exception("Status '"+str(status)+"' is not defined in TestStatus")                        
                
    
    
    def print_image_list_results(self,list=None):
        '''
        prints the image data and results for a list of eustore images. Defaults to current eustoretestsuite's list
        list - optional - list of eustore images
        '''
        if list is None:
            list = self.list
        for image in list:
            self.cur_image = image
            image.printdata()
            self.cur_image = None
        
    
            
            
            