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
from eutester.eutestcase import EutesterTestCase
from testcases.cloud_user.images.imageutils import ImageUtils
from eucaops import Eucaops
from eutester import Eutester
from eucaops.ec2ops import ResourceNotFoundException
import os
import time


class Load_Pv_Image(EutesterTestCase):

    def __init__(self, tester=None, **kwargs):
        self.emi = None
        self.eki = None
        self.eri = None
        self.setuptestcase()

        self.setup_parser(testname='load_pv_image.py',
                              description='Loads an paravirtual image from a set of '
                                          'Kernel, Ramdisk, and image by remote URLs or filepaths',
                              emi=False,
                              testlist=False)

        self.parser.add_argument('--kernel_image_url',
                                     help='URL containing the kernel image to be downloaded to the'
                                           ' worker machine and used in the pv image',
                                     default=None)
        self.parser.add_argument('--kernelfilepath',
                                     help='An existing file path on the worker machine containing '
                                          'the kernel disk image to use', default=None)

        self.parser.add_argument('--ramdisk_image_url',
                                     help='URL containing the initrd image to be downloaded to the'
                                          ' worker machine and used in the pv image',
                                     default=None)
        self.parser.add_argument('--ramdiskfilepath',
                                     help='An existing file path on the worker machine containing '
                                          'the ramdisk image to use', default=None)

        self.parser.add_argument('--disk_image_url',
                                     help='URL containing the image to be downloaded to the worker'
                                          ' machine and used for the pv disk image',
                                     default=None)
        self.parser.add_argument('--diskfilepath',
                                     help='An existing file path on the worker machine containing '
                                          'the image to use', default=None)

        self.parser.add_argument('--workerip',dest='worker_machine',
                                     help='The ip/hostname of the machine that the operation will '
                                          'be performed on', default=None)
        self.parser.add_argument('--worker_username',dest='worker_username',
                                     help='The username of the machine that the operation will be '
                                          'performed on, default:"root"', default='root')
        self.parser.add_argument('--worker_password',dest='worker_password',
                                     help='The password of the machine that the operation will be '
                                          'performed on', default=None)
        self.parser.add_argument('--worker_keypath',dest='worker_keypath',
                                     help='The ssh keypath of the machine that the operation '
                                          'will be performed on', default=None)
        self.parser.add_argument('--destpath',
                                     help='The path on the workip, that this operation will be '
                                          'performed on', default='/disk1/storage')
        self.parser.add_argument('--urlpass', dest='wget_password',
                                     help='Password needed to retrieve remote url', default=None)
        self.parser.add_argument('--urluser',dest='wget_user',
                                     help='Username needed to retrieve remote url', default=None)
        self.parser.add_argument('--interbundletime',dest='inter_bundle_timeout',
                                     help='Inter-bundle timeout', default=120)
        self.parser.add_argument('--bucket',dest='bucketname', help='bucketname', default=None)
        self.parser.add_argument('--overwrite',
                                     help='Will overwrite files in matching work dir on worker'
                                          ' machine if found', action='store_true', default=False)
        self.parser.add_argument('--no_existing_images', action='store_true', default=False,
                                 help='If set this will not use existing images found on the system'
                                      'sharing the same image name(s) for kernel(eki) '
                                      'and ramdisk(eri) images when building the final image(EMI)')
        self.parser.add_argument('--time_per_gig',
                                     help='Time allowed per image size in GB before timing out. '
                                          'Default:300 seconds', default=300)
        self.parser.add_argument('--remove_created_images',
                                     help='Flag if set will attempt to deregister'
                                          'images this test created, default:False',
                                     action='store_true', default=False)

        self.get_args()
        if (not self.args.disk_image_url and not self.args.diskfilepath) or \
                (self.args.disk_image_url and self.args.diskfilepath):
            raise ValueError('Must provide "either" a url (image_url) to a disk image or the '
                             'file path to an existing image on the worker '
                             'machine (imagefilepath)')
        if (not self.args.kernel_image_url and not self.args.kernelfilepath) or \
                (self.args.kernel_image_url and self.args.kernelfilepath):
            raise ValueError('Must provide "either" a url (kernel_image_url) to a kernel '
                             'image or the file path to an existing image on the worker '
                             'machine (kernelfilepath)')
        if (not self.args.ramdisk_image_url and not self.args.ramdiskfilepath) or \
                (self.args.ramdisk_image_url and self.args.ramdiskfilepath):
            raise ValueError('Must provide "either" a url (ramdisk_image_url) to a '
                             'ramdisk image or the file path to an existing image on the worker '
                             'machine (ramdiskfilepath)')


        self.args.worker_password = self.args.worker_password or self.args.password
        self.args.worker_keypath = self.args.worker_keypath or self.args.keypair

        self.args.virtualization_type = 'paravirtual'
        if tester is None:
            self.tester = Eucaops(config_file=self.args.config_file, password=self.args.password)
        else:
            self.tester = tester
        Eutester._EUTESTER_FORCE_ANSI_ESCAPE = self.args.use_color
        self.args.tester = self.tester
        # Allow __init__ to get args from __init__'s kwargs or through command line parser...
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        self.show_args()

        #self.args.platform = 'Linux'
        #Create an ImageUtils helper from the arguments provided in this self...
        self.image_utils = self.do_with_args(ImageUtils)

    def do_kernel_image(self):
        """
        Description:
        Registers a kernel image with the cloud for use in creating an EMI.
        Attempts to either use an existing file path or download from a URL (whichever has been
        provided by the user) to a 'worker machine'. The worker machine will default to the CLC if
        another host is not provided.
        The image is bundled, uploaded and registered using euca2ools on the worker machine.
        """
        size = None
        image_utils = self.image_utils
        kernelfilepath = self.args.kernelfilepath
        kernel_image_url = self.args.kernel_image_url
        filename = os.path.basename(kernelfilepath or kernel_image_url)
        imagename = filename[0:20] + '_by_eutester'
        try:
            image = self.tester.get_emi(emi='ki', filters={'name':imagename})
        except ResourceNotFoundException:
            image = None
        if image:
            if self.args.no_existing_images:
                x = 0
                while True:
                    try:
                         x += 1
                         newname = "{0}_{1}".format(imagename, x)
                         self.tester.get_emi(emi='ki', filters={'name':newname})
                    except ResourceNotFoundException:
                        imagename = newname
                        break
            else:
                self.status('Found existing EKI image:"{0}" with name: "{1}"'
                            .format(image.id, image.name))
                self.eki = image
                self.tester.show_image(self.eki,verbose=True)
                return self.eki
        if not kernelfilepath:
            destpath = self.args.destpath
            size, kernelfilepath = image_utils.wget_image(url=kernel_image_url,
                                                          destpath=destpath)
        manifest = image_utils.euca2ools_bundle_image(path=kernelfilepath,
                                                      destination=self.args.destpath)
        upmanifest = image_utils.euca2ools_upload_bundle(manifest=manifest,
                                                         bucketname=imagename + '_eutester_pv')
        eki = image_utils.euca2ools_register(manifest = upmanifest, name= imagename)
        # Make sure this image can be retrieved from the system...
        image = self.tester.get_emi(eki, state=None)
        assert image.id == eki, 'Image retrieved from system did not match the test image id. ' \
                                'Fix the test?'
        # Add some tags to inform the cloud admin/users where this image came from...
        image.add_tag(key='Created by eutester load_pv_image test')
        if size is not None:
            image.add_tag(key='size', value=str(size))
        if kernel_image_url:
            image.add_tag(key='source', value=kernel_image_url)
        image.update()
        self.eki = image
        self.tester.show_image(self.eki,verbose=True)
        return self.eki

    def do_ramdisk_image(self):
        """
        Description:
        Registers a ramdisk image with the cloud for use in creating an EMI.
        Attempts to either use an existing file path or download from a URL (whichever has been
        provided by the user) to a 'worker machine'. The worker machine will default to the CLC if
        another host is not provided.
        The image is bundled, uploaded and registered using euca2ools on the worker machine.
        """
        size = None
        image_utils = self.image_utils
        ramdisk_image_url = self.args.ramdisk_image_url
        ramdiskfilepath = self.args.ramdiskfilepath
        filename =  os.path.basename(ramdiskfilepath or ramdisk_image_url)
        imagename =filename[0:20] + '_by_eutester'
        try:
            image = self.tester.get_emi(emi='ri', filters={'name':imagename})
        except ResourceNotFoundException:
            image = None
        if image:
            if self.args.no_existing_images:
                x = 0
                while True:
                    try:
                         x += 1
                         newname = "{0}_{1}".format(imagename, x)
                         self.tester.get_emi(emi='ri', filters={'name':newname})
                    except ResourceNotFoundException:
                        imagename = newname
                        break
            else:
                self.status('Found existing ERI image:"{0}" with name: "{1}"'
                            .format(image.id, image.name))
                self.eri = image
                self.tester.show_image(self.eri,verbose=True)
                return self.eri
        if not ramdiskfilepath:
            destpath = self.args.destpath
            size, ramdiskfilepath = image_utils.wget_image(url=ramdisk_image_url,
                                                           destpath=destpath)
        manifest = image_utils.euca2ools_bundle_image(path=ramdiskfilepath,
                                                      destination=self.args.destpath)
        upmanifest = image_utils.euca2ools_upload_bundle(manifest=manifest,
                                                         bucketname=imagename + '_eutester_pv')
        eri = image_utils.euca2ools_register(manifest = upmanifest, name= imagename)
        # Make sure this image can be retrieved from the system...
        image = self.tester.get_emi(eri, state=None)
        assert image.id == eri, 'Image retrieved from system did not match the test image id. ' \
                                'Fix the test?'
        # Add some tags to inform the cloud admin/users where this image came from...
        image.add_tag(key='Created by eutester load_pv_image test')
        if size is not None:
            image.add_tag(key='size', value=str(size))
        if ramdisk_image_url:
            image.add_tag(key='source', value=ramdisk_image_url)
        image.update()
        self.eri = image
        self.tester.show_image(self.eri, verbose=True)
        return self.eri

    def do_image(self):
        """
        Description:
        Registers an image with the cloud using the ERI, and EKI found or created by this test.
        Attempts to either use an existing file path or download from a URL (whichever has been
        provided by the user) to a 'worker machine'. The worker machine will default to the CLC if
        another host is not provided.
        The image is bundled, uploaded and registered using euca2ools on the worker machine.
        """
        size = None
        image_utils = self.image_utils
        diskfilepath = self.args.diskfilepath
        disk_image_url = self.args.disk_image_url
        filename = os.path.basename(diskfilepath or disk_image_url)
        imagename = filename[0:20] + '_by_eutester'
        if not diskfilepath:
            destpath = self.args.destpath
            size, diskfilepath = image_utils.wget_image(url=disk_image_url,
                                                        destpath=destpath)
        try:
            self.tester.get_emi(emi='', filters={'name':imagename}, state=None)
        except ResourceNotFoundException:
            pass
        else:
            # imagename is already taken.
            # Always create a new EMI, so make sure we increment the image name...
            x = 0
            while True:
                try:
                     x += 1
                     newname = "{0}_{1}".format(imagename, x)
                     self.tester.get_emi(emi='', filters={'name':newname})
                     self.debug('image name:"{0}" is already in use...'.format(newname))
                except ResourceNotFoundException:
                    imagename = newname
                    self.debug('Found an unused image name. Using name:"{0}"'.format(imagename))
                    break
        manifest = image_utils.euca2ools_bundle_image(path=diskfilepath,
                                                      destination=self.args.destpath)
        upmanifest = image_utils.euca2ools_upload_bundle(manifest=manifest,
                                                         bucketname=imagename + '_eutester_pv')
        emi = image_utils.euca2ools_register(manifest = upmanifest,
                                                  name= imagename,
                                                  kernel=self.eki.id,
                                                  ramdisk=self.eri.id,
                                                  description='"created by eutester '
                                                              'load_pv_image test"',
                                                  virtualization_type='paravirtual',
                                                  arch='x86_64'
                                                  )
        # Make sure this image can be retrieved from the system...
        image = self.tester.get_emi(emi, state=None)
        assert image.id == emi, 'Image retrieved from system did not match the test image id. ' \
                                'Fix the test?'
        # Add some tags to inform the cloud admin/users where this image came from...
        image.add_tag(key='eutester-created', value='Created by eutester load_pv_image test')
        if size is not None:
            image.add_tag(key='size', value=str(size))
        if disk_image_url:
            image.add_tag(key='source', value=disk_image_url)
        image.update()
        self.emi = image
        self.tester.show_image(self.emi, verbose=True)
        return self.emi

    def make_image_public(self):
        """
        Description:
        Attempts to set the launch permissions to ALL, making the image public.
        """
        emi = self.tester.get_emi(self.emi, state=None)
        emi.set_launch_permissions(group_names=['all'])
        emi.update()
        self.tester.show_image(emi)

    def show_images(self):
        '''
        Attempts to fetch the EMI, EKI, and ERI created by this test and display them in table
        format to the user.
        '''
        self.debug('\nCreate the following Image(s)...\n')
        images = []
        if self.emi:
            self.emi.update()
            images.append(self.emi)
        if self.eri:
            self.eri.update()
            images.append(self.eri)
        if self.eki:
            self.eki.update()
            images.append(self.eki)
        if not images:
            self.debug('No IMAGES were created?')
        else:
            self.tester.show_images(images=images, verbose=True)
        if not self.emi and self.eri and self.eki:
            self.tester.critical('\nTEST FAILED: Could not find all images (EMI, ERI, EKI)')

    def run_new_pv_image(self):
        """
        Description:
        Attempts to run an instance from the newly created PV image.
        Will attempt to ping/ssh into the instance once running and execute the 'uptime' command.
        """
        self.reservation = None
        ### Add and authorize a group for the instance
        self.group = self.tester.add_group('load_pv_image_test')
        self.tester.authorize_group(self.group, port=22)
        self.tester.authorize_group(self.group, protocol='icmp', port=-1)
        ### Generate a keypair for the instance
        localkeys = self.tester.get_all_current_local_keys()
        if localkeys:
            self.keypair = localkeys[0]
            self.keypair_name = self.keypair.name
        else:
            self.keypair_name = "load_pv_test_keypair" + str(int(time.time()))
            self.keypair = self.tester.add_keypair(self.keypair_name)
        try:
            size = int(self.emi.tags.get('size', 0)) * int(self.args.time_per_gig)
            timeout = size or 300
            instance = self.tester.run_image(image=self.emi, keypair=self.keypair,
                                             group=self.group, timeout=timeout)[0]
            instance.sys('uptime', code=0)
            self.status("Run new PV image PASSED")
        finally:
            self.emi.update()
            self.debug('Image states after run attempt:')
            self.show_images()

    def clean_method(self):
        """
        Description:
        Attempts to clean up resources/artifacts created during this test.
        This method will not clean up the images created in this
        test. Will attempt to delete/terminate instances, keypairs, etc..
        """
        tester = self.tester
        assert isinstance(tester, Eucaops)
        tester.cleanup_artifacts(images=self.args.remove_created_images)

if __name__ == "__main__":
    testcase = Load_Pv_Image()
    # Create a single testcase to wrap and run the image creation tasks.
    test1 = testcase.create_testunit_from_method(testcase.do_kernel_image)
    test2 = testcase.create_testunit_from_method(testcase.do_ramdisk_image)
    test3 = testcase.create_testunit_from_method(testcase.do_image)
    test4 = testcase.create_testunit_from_method(testcase.make_image_public)
    test5 = testcase.create_testunit_from_method(testcase.run_new_pv_image)
    testlist = [test1, test2, test3, test4, test5]
    result = testcase.run_test_case_list(testlist,
                                         eof=True, clean_on_exit=True,
                                         printresults=True)

    if result:
        testcase.errormsg('TEST FAILED WITH RESULT:{0}'.format(result))
    else:
        testcase.status('TEST PASSED')
    exit(result)



