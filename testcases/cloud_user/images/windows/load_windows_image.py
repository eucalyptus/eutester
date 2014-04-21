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

machine=None
testcase = EutesterTestCase()

testcase.setup_parser(testname='load_hvm_image.py',
                      description='Loads an hvm image from either a remote url or local file path',
                      emi=False,
                      testlist=False)

testcase.parser.add_argument('--url',help='URL containing remote windows image to create EMI from', default=None)
testcase.parser.add_argument('--filepath',dest='filepath', help='File path to create windows EMI from', default=None)
testcase.parser.add_argument('--workerip',dest='worker_machine', help='The ip/hostname of the machine that the operation will be performed on', default=None)
testcase.parser.add_argument('--worker_username',dest='worker_username', help='The username of the machine that the operation will be performed on, default:"root"', default='root')
testcase.parser.add_argument('--worker_password',dest='worker_password', help='The password of the machine that the operation will be performed on', default=None)
testcase.parser.add_argument('--worker_keypath',dest='worker_keypath', help='The ssh keypath of the machine that the operation will be performed on', default=None)
testcase.parser.add_argument('--destpath',help='The path on the workip, that this operation will be performed on', default='/disk1/storage')
testcase.parser.add_argument('--urlpass', dest='wget_password',help='Password needed to retrieve remote url', default=None)
testcase.parser.add_argument('--urluser',dest='wget_user', help='Username needed to retrieve remote url', default=None)
testcase.parser.add_argument('--gigtime',dest='time_per_gig', help='Time allowed per gig size of image to be used', default=300)
testcase.parser.add_argument('--interbundletime',dest='inter_bundle_timeout', help='Inter-bundle timeout', default=120)
testcase.parser.add_argument('--virtualization_type', help='virtualization type, hvm or pv', default=None)
testcase.parser.add_argument('--bucket',dest='bucketname', help='bucketname', default=None)
testcase.parser.add_argument('--image_type', dest='image_type', help='"Linux" or "Windows", default: "windows"' , default="windows")
testcase.parser.add_argument('--overwrite', help='Will overwrite files in matching work dir on worker machine if found', action='store_true', default=False)

testcase.parser.add_argument('--time_per_gig', help='Time allowed per image size in GB before timing out. Default:300 seconds', default=300)

testcase.get_args()

testcase.args.worker_password = testcase.args.worker_password or testcase.args.password
testcase.args.worker_keypath = testcase.args.worker_keypath or testcase.args.keypair

if (not testcase.args.url and not testcase.args.filepath) or (testcase.args.url and testcase.args.filepath):
    raise Exception('Must specify either a URL or FILE path to create Windows EMI from')

#Set kernel to 'windows'. This result in the platform type resulting in 'windows' after registration.
if str(testcase.args.image_type).lower() == "windows":
    testcase.args.kernel = "windows"

def make_image_public():
    emi = image_utils.tester.test_resources['images'][0]
    emi.set_launch_permissions(group_names=['all'])
    testcase.debug('\n---------------------------\nCreated EMI:' + str(emi) +'\n---------------------------')

#Create an ImageUtils helper from the arguments provided in this testcase...
image_utils = testcase.do_with_args(ImageUtils)

#Create a single testcase to wrap and run the EMI creation task. Note by default all the overlapping args from
# this testcase are fed to the testunit method when ran.
test1 = testcase.create_testunit_from_method(image_utils.create_emi)
test2 = testcase.create_testunit_from_method(make_image_public)
result = testcase.run_test_case_list([test1, test2], eof=True, clean_on_exit=False, printresults=True)

#By default created resources are stored in the eucaops/tester object's test_resources dict. See if our image is
#prsent. If so print it out...
if image_utils.tester.test_resources['images']:
    emi = image_utils.tester.test_resources['images'].pop()
    testcase.debug('\n---------------------------\nCreated EMI:' + str(emi) +'\n---------------------------')

exit(result)