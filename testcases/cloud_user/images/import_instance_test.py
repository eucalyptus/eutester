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
from base64 import b64decode
import os
import time
import types


class ImportInstanceTests(EutesterTestCase):


    def __init__(self, url=None, tester=None, **kwargs):
        self.setuptestcase()
        self.setup_parser(testname='import_instance_tests',
                              description='Runs tests against import instance'
                                          'conversion tasks',
                              emi=False,
                              instance_user=False)

        self.parser.add_argument('--url',
                                 help='URL containing remote image to create '
                                      'import instance task from',
                                 default=None)

        self.parser.add_argument('--instance-user', dest='instance_user',
                                 help='Username used for ssh or winrm login. '
                                      'Defaults; Linux:"root", Windows:"Administrator"',
                                 default=None)
        self.parser.add_argument('--workerip',dest='worker_machine',
                                 help='The ip/hostname of the machine that the '
                                      'operation will be performed on',
                                 default=None)
        self.parser.add_argument('--worker_username',dest='worker_username',
                                 help='The username of the machine that the '
                                      'operation will be performed on, '
                                      'default:"root"',
                                 default='root')
        self.parser.add_argument('--worker_password',dest='worker_password',
                                 help='The password of the machine that the '
                                      'operation will be performed on',
                                 default=None)
        self.parser.add_argument('--worker_keypath',dest='worker_keypath',
                                 help='The ssh keypath of the machine that '
                                      'the operation will be performed on',
                                 default=None)
        self.parser.add_argument('--destpath',
                                 help='The path on the workip, that this '
                                      'operation will be performed on',
                                 default='/disk1/storage')
        self.parser.add_argument('--imagelocation',
                                 help='The file path on the worker of a '
                                      'pre-existing image to import',
                                 default=None)
        self.parser.add_argument('--urlpass', dest='wget_password',
                                 help='Password needed to retrieve remote url',
                                 default=None)
        self.parser.add_argument('--urluser', dest='wget_user',
                                 help='Username needed to retrieve remote url',
                                 default=None)
        self.parser.add_argument('--gigtime',dest='time_per_gig',
                                 help='Time allowed per gig size of image to '
                                      'be used',
                                 default=300)
        self.parser.add_argument('--virtualization_type',
                                 help='virtualization type, hvm or pv',
                                 default='hvm')
        self.parser.add_argument('--bucket', dest='bucketname',
                                 help='bucket name to be used for import task',
                                 default=None)
        self.parser.add_argument('--arch', dest='arch',
                                 help='Image architecture, '
                                      'ie:x86_64 (default), i386',
                                 default="x86_64")
        self.parser.add_argument('--imageformat',
                                 dest='imageformat',
                                 help='image format for import task ("vmdk", '
                                      '"raw", or "vhd")default, "raw"',
                                 default='raw')
        self.parser.add_argument('--platform', dest='platform',
                                 help='"Linux" or "Windows", default: "linux"',
                                 default="Linux")
        self.parser.add_argument('--uploaded_manifest', dest='upload_manifest',
                                 help='bucket/prefix location of manifest to '
                                      'register',
                                 default=None)
        self.parser.add_argument('--bundle_manifest', dest='bundle_manifest',
                                 help='file path on worker to bundle manifest '
                                      'to upload',
                                 default=None)
        self.parser.add_argument('--overwrite',
                                 help='Will overwrite files in matching work '
                                      'dir on worker machine if found',
                                 action='store_true', default=False)
        self.parser.add_argument('--time_per_gig',
                                 help='Time allowed (in addition to "base '
                                      'timeout") per image size in GB before '
                                      'timing out task. Default:100 seconds',
                                 default=100)
        self.parser.add_argument('--base_timeout',
                                 help='Base timeout value prior to adding '
                                      'time per gig of image size. '
                                      'Default:600 seconds',
                                 default=600)
        self.parser.add_argument('--task_user_data',
                                 help='user data to provide to import instance'
                                      'task request. '
                                      'Default:"#cloud-config\ndisable_root: '
                                      'false"',
                                 default='#cloud-config\ndisable_root: false')
        self.parser.add_argument('--no_clean_on_exit',
                                 help='Disable cleanup method upon exit to '
                                      'leave test resources behind',
                                 action='store_true', default=False)

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
        self.set_arg('tester', self.tester)
        if not self.url:
            if not self.args.url:
                raise ArgumentError(None,'Required URL not provided')
            else:
                self.url = self.args.url
        self.imagelocation = None
        self.args.worker_password = self.args.worker_password or self.args.password
        self.args.worker_keypath = self.args.worker_keypath or self.args.keypair
        # Format platform case sensitive arg.
        if str(self.args.platform).upper().strip() == "WINDOWS":
            self.args.platform = "Windows"
        elif str(self.args.platform).upper().strip() == "LINUX":
            self.args.platform = "Linux"
        if self.args.instance_user is None:
            if self.args.platform == "Windows":
                self.args.instance_user = 'Administrator'
            else:
                self.args.instance_user = 'root'
        self.latest_task_dict = None
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

    @classmethod
    def assertEquals(cls, x, y):
        assert x == y, str(x) + ' is not equal to ' + str(y)
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
        if self.args.platform == 'Windows':
            tester.authorize_group(self.group, protocol='tcp', port='3389')
            tester.authorize_group(self.group, protocol='tcp', port='80')
            tester.authorize_group(self.group, protocol='tcp', port='443')
            tester.authorize_group(self.group, protocol='tcp', port='5985')
            tester.authorize_group(self.group, protocol='tcp', port='5986')
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
            if self.imagelocation or self.url:
                location = self.imagelocation or self.url
                image_name = os.path.basename(location)[0:15]
            else:
                image_name = str(self.args.platform or 'test')
            bucketname = 'eutester_import_' + str(image_name)
        self.bucket = self.tester.s3.create_bucket(bucketname).name

    def test1_basic_create_import_instance(self,
                                          base_timout=None,
                                          time_per_gig=None):
        '''
        Definition: Attempts to run, monitor and validate the outcome of a
        basic import instance task.
        Will test the following:

        ## TASK CHECKS:
        -Euca2ools import task request
        -Will monitor task and describe task responses until complete, or a
         given timeout is reached.
        -Upon completion will validate task status

        ## TASK INSTANCE CHECKS:
        -Instance status
        -Will Monitor instance to running, then attempt to ping and ssh.
        -Instance params (security group, key, zone, etc)
        -Will request the instance from the system to confirm it is visible
        to this account, etc..

        ## TASK VOLUME CHECKS:
        -Volume status as created and available post task
        -Request the volume from the system to confirm it is visible to this
        account, etc..
        -Volume Params are correct, size, zone, etc per task request

        ## TASK SNAPSHOT CHECKS:
        -Snapshot status completed
        -Verify the owner id is the same as the account id that made the task
        request

        ## TASK IMAGE CHECKS:
        -Verify the image is not public
        -Verify the image state is 'available'
        -Verify the image owner id is the same as the account id that made the
        task request.
        '''
        base_timout = base_timout or self.args.base_timeout
        time_per_gig = time_per_gig or self.args.time_per_gig
        img_utils = self.img_utils
        tester = self.tester
        assert isinstance(img_utils, ImageUtils)
        assert isinstance(tester, Eucaops)
        params = {'import_file':self.imagelocation,
                  'bucket':self.bucket,
                  'zone':self.zone,
                  'format':self.args.imageformat,
                  'instance_type':self.args.vmtype,
                  'arch':self.args.arch,
                  'keypair':self.keyname,
                  'group':self.groupname,
                  'platform':self.args.platform,
                  'user_data':self.args.task_user_data}
        task = img_utils.euca2ools_import_instance(**params)
        assert isinstance(task,ConversionTask)
        tester.monitor_conversion_tasks(task,
                                        base_timeout=base_timout,
                                        time_per_gig=time_per_gig)

        # Make sure the task returns an instance, check that the instance for
        # proper run state and param use.
        if not task.instanceid:
            raise RuntimeError('Instance ID not found after task completed, '
                               'status msg:' + str(task.statusmessage))
        inst = tester.get_instances(idstring=task.instanceid)
        if inst:
            inst = inst[0]
            username = self.args.instance_user
            euinst = tester.convert_instance_to_euisntance(instance=inst,
                                                           keypair=self.keypair,
                                                           username=username,
                                                           auto_connect=False)
            tester.monitor_euinstances_to_running(euinst)
            if euinst.platform == 'windows':
                euinst.connect_to_instance(wait_for_boot=180, timeout=300)
            else:
                euinst.connect_to_instance()
        else:
            raise RuntimeError('Instance:"{0}" not found from task:"{1}"'
                            .format(task.instanceid, task.id))
        if not task.image_id:
            raise RuntimeError('Image Id not found after task completed, '
                               'status msg:' + str(task.statusmessage))
        emi = tester.get_emi(emi=task.image_id)
        self.assertEquals(emi.owner_id, tester.get_account_id())
        for snap in task.snapshots:
            self.assertEquals(snap.owner_id, tester.get_account_id())

        self.latest_task_dict = {'params': params,
                                 'task': task,
                                 'instance': euinst}
        return self.latest_task_dict

    def test2_validate_params_against_task(self):
        if not self.latest_task_dict:
            raise RuntimeError('Dict for latest task not found to validate?')
        params = self.latest_task_dict['params']
        task = self.latest_task_dict['task']
        return self.validate_params_against_task(params=params, task=task)

    def test3_make_image_public(self):
        if not self.latest_task_dict:
            raise RuntimeError('Dict for latest task not found to validate?')
        task = self.latest_task_dict['task']
        emi = self.tester.get_emi(emi=task.image_id)
        emi.set_launch_permissions(group_names=['all'])

    def test4_tag_image(self):
        if not self.latest_task_dict:
            raise RuntimeError('Dict for latest task not found to validate?')
        task = self.latest_task_dict['task']
        emi = self.tester.get_emi(emi=task.image_id)
        try:
            if self.url:
                emi.add_tag('source', value=(str(self.url)))
            emi.add_tag('eutester-created', value="import-instance-test")
        except Exception, te:
            self.debug('Could not add tags to image:' + str(emi.id) +
                       ", err:" + str(te))

    def validate_params_against_task(self, params, task):
        assert isinstance(params, types.DictionaryType)
        assert isinstance(task, ConversionTask)
        err_msg = ""
        try:
            if params.has_key('bucket'):
                self.debug('Checking task for bucket...')
                #todo put bucket checks here
        except Exception as e:
            self.debug(self.tester.get_traceback())
            err_msg += str(e) + "\n"

        try:
            if params.has_key('zone'):
                zone = params['zone']
                self.debug('Checking task for zone params:' + str(zone))
                self.assertEquals(zone, task.availabilityzone)
                for volume in task.volumes:
                    self.assertEquals(volume.zone, zone)
                    self.assertEquals(task.instance.placement, zone)
        except Exception as e:
            self.debug(self.tester.get_traceback())
            err_msg += str(e) + "\n"

        try:
            if params.has_key('size'):
                size = params['size']
                self.debug('Checking task for size params:' + str(size))
                self.assertEquals(zone, task.availabilityzone)
                for im_volume in task.importvolumes:
                    self.assertEquals(str(im_volume.volume.size), str(size))
        except Exception as e:
            self.debug(self.tester.get_traceback())
            err_msg += str(e) + "\n"

        try:
            if params.has_key('format'):
                image_format = params['format']
                self.debug('Checking task for format:' + str(image_format))
                for volume in task.importvolumes:
                        self.assertEquals(str(volume.image.format).upper(),
                                          str(image_format).upper())
        except Exception as e:
            self.debug(self.tester.get_traceback())
            err_msg += str(e) + "\n"

        try:
            if params.has_key('instance_type'):
                instance_type = params['instance_type']
                self.debug('Checking task for instance_type:' + str(instance_type))
                self.assertEquals(task.instance.instance_type, instance_type)
        except Exception as e:
            self.debug(self.tester.get_traceback())
            err_msg += str(e) + "\n"

        try:
            if params.has_key('arch'):
                arch = params['arch']
                self.debug('Checking task for arch:' + str(arch))
                emi = self.tester.get_emi(emi=task.image_id)
                self.assertEquals(emi.architecture, arch)
        except Exception as e:
            self.debug(self.tester.get_traceback())
            err_msg += str(e) + "\n"

        try:
            if params.has_key('keypair'):
                keypair = params['keypair']
                self.debug('Checking task for keypair:' + str(keypair))
                self.assertEquals(keypair, task.instance.key_name)
        except Exception as e:
            self.debug(self.tester.get_traceback())
            err_msg += str(e) + "\n"

        try:
            if params.has_key('group'):
                group = params['group']
                self.debug('Checking task for group:' + str(group))
                ins = self.tester.convert_instance_to_euisntance(task.instance,
                                                                 auto_connect=False)
                groups = self.tester.get_instance_security_groups(ins)
                sec_group = groups[0]
                self.assertEquals(sec_group.name, group)
        except Exception as e:
            self.debug(self.tester.get_traceback())
            err_msg += str(e) + "\n"

        try:
            if params.has_key('platform'):
                platform = params['platform']
                self.debug('Checking task for platform: ' + str(platform))
                platform = str(platform).lower()
                if platform == 'linux':
                    platform = None
                self.assertEquals(platform, task.instance.platform)
        except Exception as e:
            err_msg += str(e) + "\n"

        if err_msg:
            raise Exception("Failures in param validation detected:n\n"
                            + str(err_msg))
        try:
            if hasattr(task, 'instanceid') and task.instanceid and \
                    params.has_key('user_data'):
                user_data = params['user_data']
                self.debug('Checking task for user_data: ' + str(user_data))
                ins_attr = self.tester.ec2.get_instance_attribute(
                    task.instanceid, 'userData')
                if 'userData' in ins_attr:
                    ins_user_data = b64decode(ins_attr['userData'])
                else:
                    ins_user_data = None
                self.assertEquals(user_data, ins_user_data)
        except Exception as e:
            err_msg += str(e) + "\n"

        if err_msg:
            raise Exception("Failures in param validation detected:n\n"
                            + str(err_msg))


    def clean_method(self):
        tester = self.tester
        assert isinstance(tester, Eucaops)
        tester.cleanup_artifacts()

if __name__ == "__main__":
    testcase = ImportInstanceTests()
    if testcase.args.tests:
        list = testcase.args.tests.splitlines(',')
    else:
        list = ['test1_basic_create_import_instance',
                'test2_validate_params_against_task',
                'test3_make_image_public',
                'test4_tag_image']

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



