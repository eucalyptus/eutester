#!/usr/bin/python
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
from imageutils import ImageUtils
from eutester.sshconnection import CommandExitCodeException
from eutester.eutestcase import EutesterTestCase
from testcases.cloud_user.images.imageutils import ImageUtils
from testcases.cloud_user.images.conversiontask import ConversionTask
from boto.exception import S3ResponseError
from subprocess import CalledProcessError
from argparse import ArgumentError
import os
import time


class ImportInstanceTests(EutesterTestCase):


    def __init__(self, url=None, tester=None, **kwargs):
        self.setuptestcase()
        self.setup_parser(testname='import_instance_tests',
                              description='Runs tests against import instance'
                                          'conversion tasks',
                              emi=False)

        self.parser.add_argument('--url',help='URL containing remote image '
                                                  'to create import instance task from', default=None)
        self.parser.add_argument('--workerip',dest='worker_machine', help='The ip/hostname of the machine that the operation will be performed on', default=None)
        self.parser.add_argument('--worker_username',dest='worker_username', help='The username of the machine that the operation will be performed on, default:"root"', default='root')
        self.parser.add_argument('--worker_password',dest='worker_password', help='The password of the machine that the operation will be performed on', default=None)
        self.parser.add_argument('--worker_keypath',dest='worker_keypath', help='The ssh keypath of the machine that the operation will be performed on', default=None)
        self.parser.add_argument('--destpath',help='The path on the workip, that this operation will be performed on', default='/disk1/storage')
        self.parser.add_argument('--imagelocation',help='The file path on the worker of a pre-existing image to import', default=None)
        self.parser.add_argument('--urlpass', dest='wget_password',help='Password needed to retrieve remote url', default=None)
        self.parser.add_argument('--urluser',dest='wget_user', help='Username needed to retrieve remote url', default=None)
        self.parser.add_argument('--gigtime',dest='time_per_gig', help='Time allowed per gig size of image to be used', default=300)
        self.parser.add_argument('--virtualization_type', help='virtualization type, hvm or pv', default='hvm')
        self.parser.add_argument('--bucket',dest='bucketname', help='bucket name to be used for import task', default=None)
        self.parser.add_argument('--arch',dest='arch', help='Image architecture, ie:x86_64 (default), i386', default="x86_64")
        self.parser.add_argument('--imageformat',dest='imageformat', help='image format for import task ("vmdk", "raw", or "vhd")default, "raw"', default='raw')
        self.parser.add_argument('--platform', dest='platform', help='"Linux" or "Windows", default: "linux"' , default="Linux")
        self.parser.add_argument('--uploaded_manifest', dest='upload_manifest', help='bucket/prefix location of manifest to register' , default=None)
        self.parser.add_argument('--bundle_manifest', dest='bundle_manifest', help='file path on worker to bundle manifest to upload' , default=None)
        self.parser.add_argument('--overwrite', help='Will overwrite files in matching work dir on worker machine if found', action='store_true', default=False)
        self.parser.add_argument('--time_per_gig', help='Time allowed per image size in GB before timing out. Default:300 seconds', default=300)
        self.parser.add_argument('--no_clean_on_exit', help='Disable cleanup method upon exit to leave test resources behind', action='store_true', default=False)


        self.tester = tester
        self.url = url
        self.get_args()
        # Allow __init__ to get args from __init__'s kwargs or through command line parser...
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        self.show_args()
        # Setup basic eutester object
        if not self.tester:
            try:
                self.tester = self.do_with_args(Eucaops)
            except Exception, e:
                raise Exception('Couldnt create Eucaops tester object, make sure credpath, ' \
                                'or config_file and password was provided, err:' + str(e))
            #replace default eutester debugger with eutestcase's for more verbosity...
            self.tester.debug = lambda msg: self.debug(msg, traceback=2, linebyline=False)
        if not self.url:
            if not self.args.url:
                raise ArgumentError(None,'Required URL not provided')
            else:
                self.url = self.args.url

        self.args.worker_password = self.args.worker_password or self.args.password
        self.args.worker_keypath = self.args.worker_keypath or self.args.keypair

        #Create an ImageUtils helper from the arguments provided in this self...
        self.img_utils = self.do_with_args(ImageUtils)
        assert isinstance(self.tester, Eucaops)
        assert isinstance(self.img_utils, ImageUtils)
        self.setup()


    def setup(self):
        self.status("STARTING TEST SETUP...")
        self.get_import_bucket_to_use()
        self.get_source_volume_image()
        self.get_security_group()
        self.get_keypair()
        self.get_zone()
        self.status("TEST SETUP COMPLETE")

    @property
    def keyname(self):
        if not self.keypair:
            self.get_keypair()
        return self.keypair.name

    @property
    def groupname(self):
        if not self.group:
            self.get_security_group()
        return self.group.name

    def get_security_group(self, group_name=None):
        group_name = group_name or 'import_instance_test_group'
        tester = self.tester
        assert isinstance(tester, Eucaops)
        self.group = tester.add_group(group_name=group_name)
        #authorize group for ssh and icmp
        tester.authorize_group(self.group)
        tester.authorize_group(self.group, protocol='icmp', port='-1')
        return self.group

    def get_keypair(self):
        tester = self.tester
        assert isinstance(tester, Eucaops)
        keys = tester.get_all_current_local_keys()
        if keys:
            self.keypair = keys[0]
            self.debug('Found an existing local keypair:' + str(self.keypair))
        else:
            default_keyname = 'import_instance_test_key'+str(int(time.time()))
            try:
                local_keypath = default_keyname + ".pem"
                tester.local('ls ' + local_keypath)
                tester.local('mv ' + local_keypath + ' ' +
                             local_keypath + '_old')
            except CalledProcessError:
                pass
            self.keypair = tester.add_keypair(default_keyname)
        return self.keypair

    def get_zone(self):
        self.zone = self.args.zone
        if not self.zone:
            zones = self.tester.get_zones()
            if zones:
                self.zone = zones[0]
        if not self.zone:
            raise RuntimeError('Could not find zone to use in test')
        return self.zone

    def get_source_volume_image(self, url=None, img_utils=None):
        url = url or self.url
        img_utils = img_utils or self.img_utils
        if self.args.imagelocation:
            self.imagelocation = self.args.imagelocation
        else:
            assert isinstance(img_utils, ImageUtils)
            worker = img_utils.worker_machine
            src_img = os.path.basename(url)
            src_img = os.path.join(self.args.destpath, src_img)
            try:
                #Looking for existing file at destpath
                worker.sys('ls ' + src_img, code=0)
            except CommandExitCodeException:
                #File not found at destpath download it...
                worker.wget_remote_image(url=url, dest_file_name=src_img)
            self.imagelocation = src_img
        return self.imagelocation

    def get_import_bucket_to_use(self, bucketname=None):
        bucketname = bucketname or self.args.bucketname
        if not bucketname:
            bucketname = 'import_instance_test_bucket'
        self.bucket = self.tester.s3.create_bucket(bucketname).name

    def test_basic_create_import_instance(self):
        img_utils = self.img_utils
        tester = self.tester
        assert isinstance(img_utils, ImageUtils)
        assert isinstance(tester, Eucaops)
        task = img_utils.euca2ools_import_instance(
            import_file=self.imagelocation,
            bucket=self.bucket,
            zone=self.zone,
            format=self.args.imageformat,
            instance_type=self.args.vmtype,
            arch=self.args.arch,
            keypair=self.keyname,
            group=self.groupname,
            platform=self.args.platform)
        assert isinstance(task,ConversionTask)
        tester.monitor_conversion_tasks(task)
        inst = tester.get_instances(idstring=task.instanceid)
        if inst:
            inst = inst[0]
            username = self.args.instance_user
            euinst = tester.convert_instance_to_euisntance(instance=inst,
                                                           keypair=self.keypair,
                                                           username=username)
            tester.monitor_euinstances_to_running(euinst)
        else:
            raise Exception('Instance:"{0}" not found from task:"{1}"'
                            .format(task.instanceid, task.id))
        return euinst

    def clean_method(self):
        tester = self.tester
        assert isinstance(tester, Eucaops)
        tester.cleanup_artifacts()

if __name__ == "__main__":
    testcase = ImportInstanceTests()
    if testcase.args.tests:
        list = testcase.args.tests.splitlines(',')
    else:
        list = ['test_basic_create_import_instance']

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append(testcase.create_testunit_by_name(test))
    if testcase.args.no_clean_on_exit:
        clean_on_exit = False
    else:
        clean_on_exit = True

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,
                                         eof=False,
                                         clean_on_exit=clean_on_exit)
    exit(result)



