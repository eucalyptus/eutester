'''
Created on Apr 13, 2012

@author: clarkmatthew

example:
from eustoretests import Eustoretests
et = Eustoretests(config_file="2b_tested.lst", password="foobar")
list = et.get_uninstalled_summary()
et.install_all_images(list=list)

     eustore-install-image -h 
          -h, --help            show this help message and exit
          -i IMAGE_NAME, --image_name=IMAGE_NAME
                                name of image to install
          -t TARBALL, --tarball=TARBALL
                                name local image tarball to install from
          -s DESCRIPTION, --description=DESCRIPTION
                                description of image, mostly used with -t option
          -a ARCHITECTURE, --architecture=ARCHITECTURE
                                i386 or x86_64, mostly used with -t option
          -p PREFIX, --prefix=PREFIX
                                prefix to use when naming the image, mostly used with
                                -t option
          -b BUCKET, --bucket=BUCKET
                                specify the bucket to store the images in
          -k KERNEL_TYPE, --kernel_type=KERNEL_TYPE
                                specify the type you're using [xen|kvm]
          -d DIR, --dir=DIR     specify a temporary directory for large files
          --kernel=KERNEL       Override bundled kernel with one already installed
          --ramdisk=RAMDISK     Override bundled ramdisk with one already installed
          
          Standard Options:
            -D, --debug         Turn on all debugging output
            --debugger          Enable interactive debugger on error
            -U URL, --url=URL   Override service URL with value provided
            --region=REGION     Name of the region to connect to
            -I ACCESS_KEY_ID, --access-key-id=ACCESS_KEY_ID
                                Override access key value
            -S SECRET_KEY, --secret-key=SECRET_KEY
                                Override secret key value
            --version           Display version string
      
'''

from eucaops import Eucaops
from eutester import euinstance, euvolume
from boto.ec2.snapshot import Snapshot
import re
import time
import unittest
import inspect
import gc
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
    
        
class EustoreImage():
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
                email = ""):
        
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
        self.name = id+"_"+ver+"_"+rev+"_"+arch
        
 
 
        
        

class Eustoretests():
    acceptable_users=["eucalyptus"]
    
    
    def __init__(self, tester=None, zone=None, config_file='../input/2b_tested.lst', password="foobar",url=None, list=None, volumes=None, keypair=None, group=None, image=None, eof=1):
        if tester is None:
            self.tester = Eucaops( config_file=config_file, password = password)
        else:
            self.tester = tester
            tester.exit_on_fail = eof
            
        self.url = url
        self.url_export_string = str(" ")
        if self.url is not None:
            self.url_export_string = "export EUSTORE_URL="+str(self.url)+" &> /dev/null &&"
        if list is None:
            self.list = self.get_eustore_images()
        else:
            self.list = list
              
    def debug(self,msg):
        return self.tester.debug(msg)
    
    
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
                                email = line[ii.email]
                                )
            images.append(image)
            l += 2
        return images
            
            
    def get_system_images(self, emi=None, root_device_type=None, root_device_name=None, location=None, state="available", arch=None, owner_id=None):
        """
        Get images matching the provided criteria. 
        By default matches image location containing the  string held by the 'location' option.
        emi              (optional string ) Partial ID of the emi to return, defaults to the 'emi-" prefix to grab any
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
            
            
            
    def get_registered_image(self, eustore_image,  emi="emi-"):
        images = self.get_system_images(emi=emi, location=eustore_image.id)    
        if images == []:
            return None
        else:
            return images[0] 
            
            
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
                      timepergig=1000):
  

        image = eustore_image
        cmd = ""
        start = time.time()
        if (not force) and  (self.get_registered_image(eustore_image) is not None):
            raise Exception('Image:"'+str(image.name)+'" is already installed')
        timeout = int(image.size*timepergig)
        print "image.size:"+str(image.size)+" and timepergig:"+str(timepergig)+" = timeout:"+str(timeout)
        #build the command...
        if eucarc:
            cmd = "source eucarc && "
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
                        raise Exception("Found Error from cmd:"+str(cmd))
            else:
                raise Exception("Command exited with err:"+str(cmd))
            
            if (self.get_registered_image(eustore_image) is None):
                raise Exception('Image:"'+str(image.name)+'" is not found on system after install')
            
            self.debug(cmd+" Succeeded")  
        except Exception, e:
            raise Exception("Image:"+image.name+" failed to install"+str(e))
        
        finally:
            elapsed = int(time.time()-start)
            print "Command finish in: "+str(elapsed)+" seconds"
        
            
            
            
            
    def get_standard_opts(self,url=None,region=None,access_key=None,secret_key=None):    
            ret = ""
            if region is not None:
                ret = ret+"--region="+str(region)+" "  
            if access_key is not None:
                ret = ret+"-I "+str(access_key)+" "
            if secret_key is not None:   
                ret = ret+"-S "+str(secret_key)+" "
            return ret
        
        
    
    def install_all_images(self, hyper="both",eucarc=True, list = None):
        if list is None:
            list = self.list
        for image in list:
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
    
            
        
    def get_uninstalled_summary(self):
        '''
        Attempts to get a diff of images in our list vs what the system is reporting. 
        This relies upon the bucket location having the image id text in it. 
        Returns a list of images not believed to be on the system. Can be later passed to
        install_all_images, etc..
        '''
        retlist = []
        for image in self.list:
            self.debug("Checking to see if image:"+str(image.name)+" is installed")
            if self.get_registered_image(image) is None:
                self.debug("Image: "+str(image.name)+" not found on system")
                retlist.append(image)
            else:
                self.debug("Image: "+str(image.name)+" found installed on system")
        return retlist
            
   
        
                
            
 
            
            
            
            