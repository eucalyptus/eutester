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
import re
import time
import httplib
from xml.etree import ElementTree
import sys
from eutester.eutestcase import EutesterTestCase
from eutester.sshconnection import SshCbReturn
from eutester.machine import Machine
from conversiontask import ConversionTask


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
                 destpath=None,
                 time_per_gig=300,
                 eof=True,
                 worker_hostname=None,
                 worker_keypath=None,
                 worker_username='root',
                 worker_password=None,
                 worker_machine=None):
        self.setuptestcase()
        if not tester or not isinstance(tester, Eucaops):
            self.debug('Creating Eucaops tester obj from: config_file:"{0}", password:"{1}", '
                       'credpath:"{2}"'.format(config_file, password, credpath))
            self.tester = Eucaops(config_file=config_file, password=password, credpath=credpath)
        else:
            self.tester = tester
        self.tester.exit_on_fail = eof
        self.debugmethod = self.tester.debug

        #Setup the work machine, this is the machine which will be used for
        # performing the 'work' (download, bundle, etc)
        self.worker_keypath = worker_keypath or self.tester.keypath
        self.worker_username = worker_username
        self.worker_password = worker_password or self.tester.password
        self.worker_machine = self._get_worker_machine(worker_machine)
        if destpath is not None:
            self.destpath = str(destpath)
        else:
            self.destpath = "/disk1/storage"

        self.time_per_gig = time_per_gig
        self.credpath = credpath or self.tester.credpath

    def _get_worker_machine(self, worker):
        '''
        Attempts to verify the worker passed is a Machine() class else assume
        it's a host name of the machine work should be performed on and
        attempt to return a Machine() created from the hostname

        param: worker Machine() or 'hostname' to be used to perform image utils
        work on.
        returns Machine obj
        '''
        worker = worker or self.tester.clc
        self.debug('Verifying ')
        if isinstance(worker, Machine):
            return worker
        else:
            #Assume this is a host addr, attempt to convert it to a Machine()
            self.debug('Attempting to connect to machine: ' + str(worker) +
                       " for image utility work...")
            new_machine = Machine(hostname=worker,
                                  username=self.worker_username,
                                  password=self.worker_password,
                                  keypath=self.worker_keypath)
            return new_machine

    def getHttpRemoteImageSize(self, url, unit=None, maxredirect=5):
        return ImageUtils._getHttpRemoteImageSize(url, unit=unit, maxredirect=maxredirect)

    @staticmethod
    def _getHttpRemoteImageSize(url, unit=None, maxredirect=5, debug=None):
        '''
        Get the remote file size from the http header of the url given
        Returns size in GB unless unit is given.
        '''
        unit = unit or 1073741824
        if debug is None:
            def printdebug(msg):
                print msg
            debug = printdebug

        def get_location(url, depth, maxdepth):
            if depth > maxdepth:
                raise ValueError('Max redirects limit has been reached:{0}/{1}'
                                 .format(depth, maxdepth))
            conn = None
            try:
                url = url.replace('http://', '')
                host = url.split('/')[0]
                path = url.replace(host, '')
                debug("get_remote_file, host(" + host + ") path(" + path + ")")
                conn = httplib.HTTPConnection(host)
                conn.request("HEAD", path)
                res = conn.getresponse()
                location = res.getheader('location')
                if location and location != url:
                    depth += 1
                    debug('Redirecting: depth:{0}, url:{1}'.format(depth, location))
                    return get_location(location, depth=depth,maxdepth=maxdepth)
                else:
                    content_length = res.getheader('content-length')
                    if content_length is None:
                        raise ValueError('No content-length header found for url:{0}'
                                         .format(url))
                    fbytes = int(content_length)
                    return fbytes
            except Exception as HE:
                debug('Failed to fetch content-length header from url:{0}'.format(url))
                raise HE
            finally:
                if conn:
                    conn.close()
        try:
            fbytes = get_location(url, depth=0, maxdepth=maxredirect)
            debug("content-length:" + str(fbytes))
            if fbytes == 0:
                rfsize = 0
            else:
                rfsize = (((fbytes/unit) + 1) or 1)
            debug("Remote file size: " + str(rfsize) + "g")
        except Exception, e:
            debug("Failed to get remote file size...")
            raise e
        return rfsize

    def wget_image(self,
                   url,
                   destpath=None,
                   dest_file_name=None,
                   machine=None,
                   user=None,
                   password=None,
                   retryconn=True,
                   time_per_gig=300):
        '''
        Attempts to wget a url to a remote (worker) machine.
        :param url: url to wget/download
        :param destpath:path/dir to download to
        :param dest_file_name: filename to download image to
        :param machine: remote (worker) machine to wget on
        :param user: wget user name
        :param password: wget password
        :param retryconn: boolean to retry connection
        :param time_per_gig: int time to allow per gig of image wget'd
        :returns int size of image
        '''
        machine = machine or self.worker_machine
        if destpath is None and self.destpath is not None:
            destpath = self.destpath
        size = self.getHttpRemoteImageSize(url)
        if (size <  machine.get_available(destpath, unit=self.__class__.gig)):
            raise Exception("Not enough available space at: " +
                            str(destpath) + ", for image: " + str(url))
        timeout = size * time_per_gig
        self.debug('wget_image: ' + str(url) + ' to destpath' +
                   str(destpath) + ' on machine:' + str(machine.hostname))
        saved_location = machine.wget_remote_image(url,
                                                   path=destpath,
                                                   dest_file_name=dest_file_name,
                                                   user=user,
                                                   password=password,
                                                   retryconn=retryconn,
                                                   timeout=timeout)
        return (size, saved_location)


    def get_manifest_obj(self, path, machine=None, local=False, timeout=30):
        '''
        Read in a local or remote manifest xml file and convert to an
        xml ElementTree object.
        :param path: local or remote path to manifest file
        :param machine: the remote machine to read manifest file from
        :param local: boolean to determine if file is local
        :param timeout: timeout in second for reading in file
        :returns xml ElementTree obj
        '''
        cmd = 'cat ' + str(path)
        if not local:
            machine = machine or self.worker_machine
            out = machine.cmd(cmd, timeout=timeout, verbose=False)
            if out['status'] != 0:
                raise Exception('get_manifest_part_count failed, cmd status:'
                                + str(out['status']))
            output = out['output']
        else:
            output = self.tester.sys(cmd, timeout=timeout,
                                  listformat=False, code=0)
        xml = ElementTree.fromstring(output)
        return xml

    def get_manifest_part_count(self,
                                path,
                                machine=None,
                                local=False,
                                timeout=30):
        '''
        Attempt retrieve the part count value from a manifest file
        :param path: local or remote path to manifest file
        :param machine: the remote machine to read manifest file from
        :param local: boolean to determine if file is local
        :param timeout: timeout in second for reading in file
        :returns int count
        '''
        manifest_xml = self.get_manifest_obj(path=path,
                                             machine=machine,
                                             local=local,
                                             timeout=timeout)
        image = manifest_xml.find('image')
        parts = image.find('parts')
        part_count = parts.get('count')
        self.debug('get_manifest_part_count:' + str(path) +
                   ', count:' + str(part_count))
        return int(part_count)

    def get_manifest_image_name(self,
                                path,
                                machine=None,
                                local=False,
                                timeout=30):
        '''
        Attempts to read the image name from a manifest file
        :param path: local or remote path to manifest file
        :param machine: the remote machine to read manifest file from
        :param local: boolean to determine if file is local
        :param timeout: timeout in second for reading in file
        :returns string image name
        '''
        manifest_xml = self.get_manifest_obj(path=path,
                                             machine=machine,
                                             local=local,
                                             timeout=timeout)
        image = manifest_xml.find('image')
        name_elem = image.find('name')
        return name_elem.text
    
    def euca2ools_bundle_image(self,
                     path,
                     machine=None,
                     machine_credpath=None,
                     prefix=None,
                     kernel=None,
                     ramdisk=None,
                     block_device_mapping=None,
                     destination='/disk1/storage',
                     arch='x86_64',
                     debug=False,
                     interbundle_timeout=120, 
                     time_per_gig=None):
        '''
        Bundle an image on a 'machine'.
        where credpath to creds on machine
        '''
        self.status('Starting euca2ools_bundle_image at path:"{0}"'.format(path))
        time_per_gig = time_per_gig or self.time_per_gig
        credpath = machine_credpath or self.credpath
        machine = machine or self.worker_machine
        image_size = machine.get_file_size(path)/self.gig or 1
        timeout = time_per_gig * image_size
        cbargs = [timeout, interbundle_timeout, time.time(), 0, True]
        if destination is None:
            destination = machine.sys('pwd')[0]
        freesize = machine.get_available(str(destination), (self.gig/self.kb))
        if (freesize < image_size):
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
            cmdargs = cmdargs + " --block-device-mapping " + \
                      str(block_device_mapping)
        if destination:
            cmdargs = cmdargs + " --destination " + str(destination)
        if arch:
            cmdargs = cmdargs + " --arch " + str(arch)
        if debug:
            cmdargs = cmdargs + " --debug "
        
        cmdargs = cmdargs + " -i " + str(path)

        if credpath is not None:
            cmd = 'source ' + str(credpath) + '/eucarc && euca-bundle-image ' \
                  + str(cmdargs)
        else:
            skey = self.tester.get_secret_key()
            akey = self.tester.get_access_key()
            cmd = 'euca-bundle-image -a ' + str(akey) + ' -s ' + \
                  str(skey) + str(cmdargs)
        #execute the command  
        out = machine.cmd(cmd, timeout=timeout, listformat=True,
                          cb = self._bundle_status_cb, cbargs=cbargs)
        if out['status'] != 0:
            raise Exception('bundle_image "' + str(path) +
                            '" failed. Errcode:' + str(out['status']))
        manifest = None
        for line in out['output']:
            line = str(line)
            if re.search("(Generating|Wrote) manifest",line):
                manifest = line.split()[2]
                break
        if manifest is None:
            raise Exception('Failed to find manifest from bundle_image:' +
                            str(path))
        self.debug('bundle_image:'+str(path)+'. manifest:'+str(manifest))
        return manifest

    def euca2ools_upload_bundle(self,
                      manifest, 
                      machine=None,
                      bucketname=None, 
                      machine_credpath=None,
                      debug=False, 
                      interbundle_timeout=120, 
                      timeout=0, 
                      image_check_timeout=300,
                      uniquebucket=True):
        '''
        Bundle an image on a 'machine'.
        where credpath to creds on machine
        '''
        self.status('Starting euca2ools_upload_bundle for manifest:"{0}"'.format(manifest))
        machine = machine or self.worker_machine
        credpath = machine_credpath or self.credpath
        cbargs = [timeout, interbundle_timeout, time.time(), 0, True]
        bname = ''
        cmdargs = ""
        manifest = str(manifest)
        upmanifest = None
        part_count = -1
        try:
            part_count = self.get_manifest_part_count(manifest, machine=machine)
        except:
            pass
        self.debug('Attempting to upload_bundle:' + str(manifest) +
                   ", bucketname:" + str(bucketname) + ", part_count:" +
                   str(part_count))
        if bucketname:
            bname = bucketname
            if uniquebucket:
                bname = self._get_unique_bucket_name(bname)
        else:
            #Use the image name found in the manifest as bucketname
            bname = self._generate_unique_bucket_name_from_manifest(
                manifest, unique=uniquebucket)
        self.debug('Using upload_bundle bucket name: '+str(bname))
        cmdargs = cmdargs + " -b " +str(bname)
        if debug:
            cmdargs = cmdargs + " --debug "
        cmdargs = cmdargs + " -b " + str(bname) + " -m " +str(manifest)
        if credpath is not None:
            cmd = 'source ' + str(credpath) + '/eucarc && euca-upload-bundle '\
                  + str(cmdargs)
        else:
            skey = self.tester.get_secret_key()
            akey = self.tester.get_access_key()
            cmd = 'euca-upload-bundle -a '+str(akey) + ' -s ' + \
                  str(skey) + str(cmdargs)
        #execute upload-bundle command...
        out = machine.cmd(cmd, timeout=image_check_timeout, listformat=True,
                          cb=self._bundle_status_cb, cbargs=cbargs)
        if out['status'] != 0:
            raise Exception('upload_bundle "' + str(manifest) +
                            '" failed. Errcode:' + str(out['status']))
        for line in out['output']:
            line = str(line)
            if re.search('Uploaded', line) and re.search('manifest', line):
                upmanifest = line.split().pop()
                break
        if upmanifest is None:
            raise Exception('Failed to find upload manifest from '
                            'upload_bundle command')
        self.debug('upload_image:'+str(manifest)+'. manifest:'+str(upmanifest))
        return upmanifest

    def euca2ools_bundle_and_upload(self,
                                    file,
                                    arch,
                                    bucket,
                                    prefix=None,
                                    directory=None,
                                    kernel=None,
                                    ramdisk=None,
                                    block_device_map=[],
                                    product_codes=None,
                                    acl=None,
                                    location=None,
                                    ):
        raise NotImplemented('euca2ools_bundle_and_upload wrapper '
                             'not implemented yet')

    def euca2ools_register(self,
                           manifest,
                           name,
                           description=None,
                           arch=None,
                           kernel=None,
                           ramdisk=None,
                           root_device_name=None,
                           snapshot_id=None,
                           block_dev_map=[],
                           virtualization_type=None,
                           platform=None,
                           machine=None,
                           machine_credpath=None):
        self.status('Starting euca2ools_register for manifest:"{0}", kernel:"{1}", ramdisk:"{2}"'
                    .format(manifest, kernel,ramdisk))

        machine = machine or self.worker_machine
        credpath = machine_credpath or self.credpath
        cmdargs = str(manifest) + " -n " + str(name)
        emi = None
        if description:
            cmdargs += ' -d ' + str(description)
        if arch:
            cmdargs += ' -a ' + str(arch)
        if kernel:
            cmdargs += ' --kernel ' + str(kernel)
        if ramdisk:
            cmdargs += ' --ramdisk ' + str(ramdisk)
        if root_device_name:
            cmdargs += ' --root-device-name ' + str(root_device_name)
        if snapshot_id:
            cmdargs += ' -s ' + str(snapshot_id)
        for dev in block_dev_map:
            cmdargs += ' -b ' + str(dev)
        if virtualization_type:
            cmdargs += ' --virtualization-type ' + str(virtualization_type)
        if platform:
            cmdargs += ' --platform ' + str(platform)

        if credpath is not None:
            cmd = 'source ' + str(credpath) + '/eucarc && euca-register '\
                  + str(cmdargs)
        else:
            skey = self.tester.get_secret_key()
            akey = self.tester.get_access_key()
            cmd = ('euca-upload-register -a ' + str(akey) +
                   ' -s ' + str(skey) + str(cmdargs))
        out = machine.sys(cmd=cmd, code=0)
        for line in out:
            if re.search('IMAGE',line):
                emi = line.split().pop().strip()
        assert emi, 'Invalid emi value: "' + str(emi) + '"'
        self.tester.test_resources["images"].append(self.tester.ec2.get_all_images([emi])[0])
        return emi

    def euca2ools_download_bundle(self,
                                  bucket,
                                  manifest=None,
                                  prefix=None,
                                  directory=None,
                                  image_name=None,
                                  machine=None,
                                  machine_credpath=None,
                                  ):
        machine = machine or self.worker_machine

        credpath = machine_credpath or self.credpath
        cmdargs = " -b " + str(bucket)
        if manifest:
            cmdargs += " -m " + str(manifest)
        if prefix:
            cmdargs += " -p " + str(prefix)
        if directory:
            cmdargs += " -d " + str(directory)
        if credpath is not None:
            cmd = 'source ' + str(credpath) + \
                  '/eucarc && euca-download-bundle '\
                  + str(cmdargs)
        else:
            skey = self.tester.get_secret_key()
            akey = self.tester.get_access_key()
            cmd = ('euca-download-bundle -a ' + str(akey) +
                   ' -s ' + str(skey) + str(cmdargs))
        out = machine.sys(cmd=cmd, code=0)



        raise NotImplemented('euca2ools_download_bundle wrapper '
                             'not implemented yet')

    def euca2ools_download_and_unbundle(self,
                                        bucket,
                                        manifest=None,
                                        prefix=None,
                                        directory=None,
                                        maxbytes=None,
                                        ):
        raise NotImplemented('euca2ools_download_and_unbundle wrapper'
                             ' not implemented yet')


    def euca2ools_import_volume(self,
                                import_file,
                                bucket,
                                zone,
                                format,
                                size=None,
                                presigned_manifest_url=None,
                                prefix=None,
                                days=None,
                                no_upload=None,
                                description=None,
                                s3_url=None,
                                ec2_url=None,
                                owner_sak=None,
                                owner_akid=None,
                                security_token=None,
                                machine=None,
                                machine_credpath=None,
                                misc=None):
        '''
        Note: Under normal conditions this will create a volume that may
        not be available to the returned task object immediately. The volume
        id will be available later by using task.update() on the returned
        task object. For this reason the volume is not being added to
        the tester's resources list here.
        '''
        machine = machine or self.worker_machine
        credpath = machine_credpath or self.credpath
        cmdargs = str(import_file) + " -b " + str(bucket) + \
                  " -z " + str(zone) + " -f " + str(format) + \
                  " --show-empty-fields "
        emi = None
        if description:
            cmdargs += ' -d ' + str(description)
        if size:
            cmdargs += ' -s ' + str(size)
        if presigned_manifest_url:
            cmdargs += ' --manifest-url ' + str(presigned_manifest_url)
        if prefix:
            cmdargs += " --prefix " + str(prefix)
        if days:
            cmdargs += " -x " + str(days)
        if no_upload:
            cmdargs += " --no-upload "
        if s3_url:
            cmdargs += " --s3-url " + str(s3_url)
        if ec2_url:
            cmdargs += " -U " + str(ec2_url)
        if owner_sak:
            cmdargs += " -w " + str(owner_sak)
        if owner_akid:
            cmdargs += " -o " + str(owner_akid)
        if security_token:
            cmdargs += " --security-token " + str(security_token)
        if misc:
            cmdargs += misc
        if credpath is not None:
            cmd = ('source ' + str(credpath) +
                   '/eucarc && euca-import-volume ' +
                   str(cmdargs))
        else:
            cmd = 'euca-upload-import-volume '
            # if keys were not already applied to args, fetch and populate
            # them now.
            if not owner_sak:
                owner_sak = self.tester.get_secret_key()
                cmdargs += " -w " + str(owner_sak)
            if not owner_akid:
                owner_akid = self.tester.get_access_key()
                cmdargs += " -o " + str(owner_akid)
            cmd += str(cmdargs)
        out = machine.sys(cmd=cmd, code=0)
        for line in out:
            lre = re.search('import-vol-\w{8}', line)
            if lre:
                taskid = lre.group()
        self.debug('Import taskid:' + str(taskid))
        #check on system using describe...
        task = self.tester.get_conversion_task(taskid=taskid)
        assert task, 'Task not found in describe conversion tasks. "{0}"'\
            .format(str(taskid))
        self.tester.test_resources['volumes']
        return task


    def euca2ools_import_instance(self,
                                import_file,
                                bucket,
                                zone,
                                format,
                                instance_type,
                                arch,
                                platform,
                                size=None,
                                keypair=None,
                                presigned_manifest_url=None,
                                prefix=None,
                                days=None,
                                no_upload=None,
                                description=None,
                                group=None,
                                s3_url=None,
                                ec2_url=None,
                                image_size=None,
                                user_data=None,
                                user_data_file=None,
                                private_addr=None,
                                shutdown_behavior=None,
                                owner_sak=None,
                                owner_akid=None,
                                security_token=None,
                                machine=None,
                                machine_credpath=None,
                                misc=None,
                                time_per_gig=90):
        machine = machine or self.worker_machine
        try:
            file_size = machine.get_file_size(import_file)
            gb = file_size/self.gig or 1
            timeout = gb * time_per_gig
        except:
            timeout = 300
        credpath = machine_credpath or self.credpath
        cmdargs = str(import_file) + " -b " + str(bucket) + \
                  " -z " + str(zone) + " -f " + str(format) + \
                  " -t " + str(instance_type) + " -a " + str(arch) + \
                  " -p " + str(platform) + \
                  " --show-empty-fields "
        emi = None
        if description:
            cmdargs += ' -d ' + str(description)
        if group:
            cmdargs += ' -g ' + str(group)
        if keypair:
            cmdargs += ' --key ' + str(keypair)
        if size:
            cmdargs += ' -s ' + str(size)
        if presigned_manifest_url:
            cmdargs += ' --manifest-url ' + str(presigned_manifest_url)
        if prefix:
            cmdargs += " --prefix " + str(prefix)
        if days:
            cmdargs += " -x " + str(days)
        if no_upload:
            cmdargs += " --no-upload "
        if s3_url:
            cmdargs += " --s3-url " + str(s3_url)
        if ec2_url:
            cmdargs += " -U " + str(ec2_url)
        if image_size:
            cmdargs += " --image-size " + str(image_size)
        if user_data:
            cmdargs += ' --user-data "' + str(user_data) +'"'
        if user_data_file:
            cmdargs += " --user-data-file " + str(user_data_file)
        if private_addr:
            cmdargs += " --private-ip-address"
        if shutdown_behavior:
            cmdargs += " --instance-initiated-shutdown-behavior " + \
                        str(shutdown_behavior)
        if owner_sak:
            cmdargs += " -w " + str(owner_sak)
        if owner_akid:
            cmdargs += " -o " + str(owner_akid)
        if security_token:
            cmdargs += " --security-token " + str(security_token)
        if misc:
            cmdargs += misc
        if credpath is not None:
            cmd = ('source ' + str(credpath) +
                   '/eucarc && euca-import-instance ' +
                   str(cmdargs))
        else:
            cmd = 'euca-upload-import-volume '
            # if keys were not already applied to args, fetch and populate
            # them now.
            if not owner_sak:
                owner_sak = self.tester.get_secret_key()
                cmdargs += " -w " + str(owner_sak)
            if not owner_akid:
                owner_akid = self.tester.get_access_key()
                cmdargs += " -o " + str(owner_akid)
            cmd += str(cmdargs)
        out = machine.sys(cmd=cmd, timeout=timeout, code=0)
        taskid = None
        for line in out:
            lre = re.search('import-i-\w{8}', line)
            if lre:
                taskid = lre.group()
        if not taskid:
            raise RuntimeError('Could not find a task id in output from cmd:'
                               + str(cmd))
        self.debug('Import taskid:' + str(taskid))
        #check on system using describe...
        task = self.tester.get_conversion_task(taskid=taskid)
        assert task, 'Task not found in describe conversion tasks. "{0}"'\
            .format(str(taskid))
        return task

    def _parse_euca2ools_conversion_task_output(self, output):
        splitlist = []
        retlist = []
        for line in output:
            splitlist.extend(line.split('\t'))
        if len(splitlist) % 2:
            raise ValueError("Conversion task output:\n" + str(output) +
                             '\nParsed euca2ools conversion task output does '
                             'not have an even number of fields to parse')
        #Build out a dict based upon the key value-ish format of the output
        task = ConversionTask()
        for i in xrange(0, len(splitlist)):
            if i % 2:
                task.endElement(name=lastkey,value=splitlist[i])
            else:
                lastkey = str(splitlist[i]).lower()
                if lastkey == 'tasktype':
                    if task:
                        retlist.append(task)
                    task = ConversionTask
        return retlist

    def _generate_unique_bucket_name_from_manifest(self,manifest, unique=True):
        mlist = str(manifest.replace('.manifest.xml', '')).split('/')
        basename = mlist[len(mlist)-1].replace('_', '').replace('.', '')
        if unique:
            return self._get_unique_bucket_name(basename)
        return basename

    def _get_unique_bucket_name(self, basename, id='test', start=0):
        bx=start
        bname = basename
        while self.tester.get_bucket_by_name(bname) is not None:
            bx += 1
            bname = basename+str(id)+str(bx)
        return bname


    def create_working_dir_on_worker_machine(self, path, overwrite=False):
        path = str(path)
        if self.worker_machine.is_file_present(path):
            if not overwrite:
                raise Exception('Dir found on:' +
                                str(self.worker_machine.hostname) +
                                ',"' + path + '".\n' +
                                'Either remove conflicting files, '
                                'use "filepath" option or "overwrite"')
        else:
            self.worker_machine.sys('mkdir -p ' + path, code=0)


    def _bundle_status_cb(self, buf, cmdtimeout, parttimeout, starttime,
                         lasttime, check_image_stage):
        ret = SshCbReturn(stop=False)
        #if the over timeout or the callback interval has expired,
        # then return stop=true
        #interval timeout should not be hit due to the setting of the
        # timer value, but check here anyways
        
        if (cmdtimeout != 0) and ( int(time.time()-starttime) > cmdtimeout):
            self.debug('bundle_status_cb command timed out after ' +
                       str(cmdtimeout)+' seconds')
            ret.statuscode=-100 
            ret.stop = True
            return ret
        if not check_image_stage:
            ret.settimer = parttimeout
            if (parttimeout != 0 and lasttime != 0) and \
                    (int(time.time()-lasttime) > parttimeout):
                self.debug('bundle_status_cb inter-part time out after ' +
                           str(parttimeout) + ' seconds')
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
        #Command is still going, reset timer thread to intervaltimeout,
        # provide arguments for  next time this is called from ssh cmd.
        ret.stop = False
        ret.nextargs =[cmdtimeout, parttimeout, starttime,
                       time.time(), check_image_stage]
        return ret

    def create_emi(self,
                    url,
                    machine=None,
                    bucketname=None,
                    machine_credpath=None,
                    debug=False,
                    prefix=None,
                    kernel=None,
                    ramdisk=None,
                    architecture=None,
                    block_device_mapping=[],
                    destpath=None,
                    root_device_name=None,
                    description=None,
                    virtualization_type=None,
                    platform=None,
                    name=None,
                    interbundle_timeout=120,
                    upload_timeout=0,
                    uniquebucket=True,
                    wget_user=None,
                    wget_password=None,
                    wget_retryconn=True,
                    filepath=None,
                    bundle_manifest=None,
                    upload_manifest=None,
                    time_per_gig=300,
                    tagname=None,
                    overwrite=False
                    ):
        start = time.time()
        filesize = None
        destpath = destpath or self.destpath
        destpath = str(destpath)
        if not destpath.endswith('/'):
            destpath += '/'
        if url:
            filename = str(url).split('/')[-1]
            destpath = destpath + str(filename.replace('.','_'))
        self.debug('create_emi_from_url:' + str(url) + ", starting...")
        if filepath is None and bundle_manifest is None and \
                        upload_manifest is None:
            filepath = destpath + "/" + str(filename)
            self.create_working_dir_on_worker_machine(path=destpath,
                                                      overwrite=overwrite)

            self.debug('Downloading image to ' + str(machine) + ':' +
                       str(filepath) + ', url:' + str(url))
            filesize = self.wget_image(url,
                                       destpath=destpath,
                                       machine=machine,
                                       user=wget_user,
                                       password=wget_password,
                                       retryconn=wget_retryconn,
                                       time_per_gig=time_per_gig)
            
        self.status('create_emi_from_url: Image downloaded to machine, '
                    'now bundling image...')
        if bundle_manifest is None and upload_manifest is None:
            bundle_manifest = self.euca2ools_bundle_image(
                filepath,
                machine=machine,
                machine_credpath=machine_credpath,
                prefix=prefix,
                kernel=kernel,
                ramdisk=ramdisk,
                block_device_mapping=block_device_mapping,
                destination=destpath,
                debug=debug,
                interbundle_timeout=interbundle_timeout,
                time_per_gig=time_per_gig)
        
        self.status('create_emi_from_url: Image bundled, now uploading...')
        if upload_manifest is None:
            upload_manifest = self.euca2ools_upload_bundle(
                bundle_manifest,
                machine=machine,
                bucketname=bucketname,
                machine_credpath=machine_credpath,
                debug=debug,
                interbundle_timeout=interbundle_timeout,
                timeout=upload_timeout,
                uniquebucket=uniquebucket)
        
        self.status('create_emi_from_url: Now registering...')
        if name is None:
            name = upload_manifest.split('/').pop().rstrip('manifest.xml')
            name = "".join(re.findall(r"\w", name))
            name += '-' + str(int(time.time()))
        try:
            self.tester.get_emi(name='name')
        except:
            name += 'X'
        emi = self.euca2ools_register(
            manifest=upload_manifest,
            name=name,
            description=description,
            arch=architecture,
            kernel=kernel,
            ramdisk=ramdisk,
            root_device_name=root_device_name,
            block_dev_map=block_device_mapping,
            virtualization_type=virtualization_type,
            platform=platform)
        self.debug('euca2ools_register returned:"' + str(emi) +
                   '", now verify it exists on the cloud...')

        #Verify emi exists on the system, and convert to boto obj...
        emi = self.tester.get_emi(emi)

        #Add tags that might have test use meaning...
        try:
            if filesize is not None:
                emi.add_tag('size', value= str(filesize))
            if url:
                emi.add_tag('source', value=(str(url)))
            emi.add_tag(tagname or 'eutester-created')
        except Exception, te:
            self.debug('Could not add tags to image:' + str(emi.id) +
                       ", err:" + str(te))
        elapsed= int(time.time()-start)
        self.status('create_emi_from_url: Done, image registered as:' +
                    str(emi.id) + ", after " + str(elapsed) + " seconds")
        return emi

