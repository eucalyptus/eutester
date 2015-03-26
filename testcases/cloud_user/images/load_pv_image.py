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
import os


class Load_Pv_image(EutesterTestCase):

    def __init__(self, tester=None, **kwargs):
        self.emi = None
        self.eki = None
        self.eri = None
        self.setuptestcase()
        self.setup_parser()

        self.setup_parser(testname='load_pv_image.py',
                              description='Loads an paravirtual image from a set of '
                                          'Kernel, Ramdisk, and image by remote URLs or filepaths',
                              emi=False,
                              testlist=False)

        self.parser.add_argument('--kernel_image_url',
                                     help='URL containing the kernel image to be downloaded to the'
                                           ' worker machine and used in the pv image',
                                     default=None)
        self.parser.add_argument('--kernelfilepath',dest='filepath',
                                     help='An existing file path on the worker machine containing '
                                          'the kernel disk image to use', default=None)

        self.parser.add_argument('--ramdisk_image_url',
                                     help='URL containing the initrd image to be downloaded to the'
                                          ' worker machine and used in the pv image',
                                     default=None)
        self.parser.add_argument('--ramdiskfilepath',dest='ramdiskfilepath',
                                     help='An existing file path on the worker machine containing '
                                          'the ramdisk image to use', default=None)

        self.parser.add_argument('--disk_image_url',
                                     help='URL containing the image to be downloaded to the worker'
                                          ' machine and used for the pv disk image',
                                     default=None)
        self.parser.add_argument('--imagefilepath',dest='diskfilepath',
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
        self.parser.add_argument('--gigtime',dest='time_per_gig',
                                     help='Time allowed per gig size of image to be used',
                                     default=300)
        self.parser.add_argument('--interbundletime',dest='inter_bundle_timeout',
                                     help='Inter-bundle timeout', default=120)
        self.parser.add_argument('--bucket',dest='bucketname', help='bucketname', default=None)
        self.parser.add_argument('--overwrite',
                                     help='Will overwrite files in matching work dir on worker'
                                          ' machine if found', action='store_true', default=False)
        self.parser.add_argument('--time_per_gig',
                                     help='Time allowed per image size in GB before timing out. '
                                          'Default:300 seconds', default=300)

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
        self.args.tester = tester
        # Allow __init__ to get args from __init__'s kwargs or through command line parser...
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        self.show_args()

        #self.args.platform = 'Linux'
        #Create an ImageUtils helper from the arguments provided in this self...
        self.image_utils = self.do_with_args(ImageUtils)
        self.image_utils = ImageUtils()
        self.debug('remove this line') and exit(1)

    def do_kernel_image(self):
        image_utils = self.image_utils
        kernelfilepath = self.args.kernelfilepath
        if not kernelfilepath:
            filename = os.path.basename(self.args.kernel_image_url)
            destpath = self.args.destpath
            image_utils.wget_image(url=self.args.kernel_image_url,
                                   dest_file_name=filename,
                                   destpath=destpath)
            kernelfilepath = os.path.join(destpath, filename)
        imagename = os.path.basename(kernelfilepath)[0,20] + '_by_eutester'
        manifest = image_utils.euca2ools_bundle_image(file=kernelfilepath)
        upmanifest = image_utils.euca2ools_upload_bundle(manifest=manifest)
        self.eki = image_utils.euca2ools_register(manifest = upmanifest, name= imagename)
        return self.eki

    def do_ramdisk_image(self):
        image_utils = self.image_utils
        ramdiskfilepath = self.args.ramdiskfilepath
        if not ramdiskfilepath:
            filename = os.path.basename(self.args.ramdisk_image_url)
            destpath = self.args.destpath
            image_utils.wget_image(url=self.args.kernel_image_url,
                                   dest_file_name=filename,
                                   destpath=destpath)
            ramdiskfilepath = os.path.join(destpath, filename)
        imagename = os.path.basename(ramdiskfilepath)[0,20] + '_by_eutester'
        manifest = image_utils.euca2ools_bundle_image(file=ramdiskfilepath)
        upmanifest = image_utils.euca2ools_upload_bundle(manifest=manifest)
        self.eri = image_utils.euca2ools_register(manifest = upmanifest, name= imagename)
        return self.eri

    def do_image(self):
        image_utils = self.image_utils
        diskfilepath = self.args.diskfilepath
        if not diskfilepath:
            filename = os.path.basename(self.args.disk_image_url)
            destpath = self.args.destpath
            image_utils.wget_image(url=self.args.disk_image_url,
                                   dest_file_name=filename,
                                   destpath=destpath)
            diskfilepath = os.path.join(destpath, filename)
        imagename = os.path.basename(diskfilepath)[0,20] + '_by_eutester'
        manifest = image_utils.euca2ools_bundle_image(file=diskfilepath)
        upmanifest = image_utils.euca2ools_upload_bundle(manifest=manifest)
        emi = image_utils.euca2ools_register(manifest = upmanifest,
                                                  name= imagename,
                                                  kernel=self.eki,
                                                  ramdisk=self.eri,
                                                  description='created by eutester load_pv_image test',
                                                  virtualization_type='paravirtual',
                                                  arch='x86_64'
                                                  )
        self.emi = self.tester.get_emi(emi)
        self.debug('\n---------------------------\nCreated EMI:' + str(emi) +
                   '\n---------------------------')
        return self.emi

    def tag_image(self):
        emi = self.tester.get_emi(self.emi)
        emi.add_tag('Created by eutester load_pv_image test')

    def make_image_public(self):
        emi = self.tester.get_emi(self.emi)
        emi.set_launch_permissions(group_names=['all'])

    def show_images(self):
        self.debug('\nCreate the following Image(s)...\n')
        images = []
        if self.emi:
            images.append(self.emi)
        if self.eri:
            images.append(self.eri)
        if self.eki:
            images.append(self.eki)
        if not images:
            self.debug('No IMAGES were created?')
        else:
            self.tester.show_images(images=images)




if __name__ == "__main__":
    testcase = Load_Pv_image()
    #Create a single testcase to wrap and run the EMI creation task. Note by default all the
    # overlapping args from this testcase are fed to the testunit method when ran.
    test1 = testcase.create_testunit_from_method(testcase.do_kernel_image)
    test2 = testcase.create_testunit_from_method(testcase.do_ramdisk_image)
    test3 = testcase.create_testunit_from_method(testcase.do_image)
    test4 = testcase.create_testunit_from_method(testcase.tag_image)
    test5 = testcase.create_testunit_from_method(testcase.make_image_public)

    result = testcase.run_test_case_list([test1, test2, test3, test4, test5],
                                         eof=True, clean_on_exit=False,
                                         printresults=True)

    # Show the images that were created in this test (if any)
    testcase.show_images()
    exit(result)



