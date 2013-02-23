#!/usr/bin/env python
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


#
##########################
#                        #
#       Test Cases       #
#                        #
##########################
#
#    "running_test" - verify image-instance goes to running 
#    "metadata_test" - verify basic cloud metadata service can be used from this image-instance
#    "user_test" = verify that only login users provided in userlist exist on this image-instance
#    "root_test" - verify that a root password is not set, unless one is given
#    "attach_volume_test" - verify volcount number of volumes can be attached, and appear within this instance
#    "detach_volume_test" - verify attached volumes can be detached, guest dev is removed
#    "reboot_test" - verify instance can be rebooted, ssh re-established, any volumes remain attached
#    "terminate_test" - verify instance goes to proper instance state
#    "ssh_test" - verify an ssh session can be established with this instance once running
#    "zeroconf_test"= verify zero conf is disaabled on the image
#    "virtiopresent_test" - verify that the virtio mods are available on this image
#
#    @author: clarkmatthew

import unittest
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import EutesterTestResult
from eustoretestsuite import Eustoretestsuite
import os
import argparse

testsuite = None
zone = None
config_file = None
password = None
credpath = None
keypair = None
group = None
emi = None
image = None
vmtype = None
userlist = None
xof = None
volcount = None
rootpass = None


class emi_tests(unittest.TestCase):
    
    def setUp(self):
        '''
        Main function of setup is to instantiate an Eustore Test Suite object. With command line args. 
        '''
        testsuite = self.testsuite = Eustoretestsuite( config_file=config_file, 
                                           password=password,
                                           keypair=keypair, 
                                           group=group,  
                                           zone=zone,
                                           credpath=credpath )
        
    def test_emi_suite(self):
        '''
        Full suite of image specific tests
        '''
        testsuite = self.testsuite
        images = testsuite.get_system_images(emi = emi)
        if len(images) != 1:
            raise exception('('+str(len(images))+') != (1) image matches for emi string:'+str(emi) )
        image = self.image = testsuite.convert_image_list_to_eustore_images(images)[0]
        self.testsuite.run_image_test_suite(image, vmtype=vmtype, zone=zone, userlist=userlist, rootpass=rootpass, xof=xof, volcount=volcount)
        
        
    def tearDown(self):
        '''
        Clean up resource created during test, output results
        '''
        try:
            self.testsuite.clean_up_running_instances_for_image(image)
        except:
            self.testsuite.debug("Cleanup failed. Exiting normally")
        finally:
            #print the image test results
            self.image.printdata()
            
        
            
    


if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(prog="emi_basic_test.py",
                                     version="Test Case [emi_basic_test.py] Version 0.1",
                                     description="Attempts to tests and provide info on specific areas of a\
                                     a given registered image.",
                                     usage="%(prog)s --emi  --credpath <path to creds> <...options> ")
    
    
    
    parser.add_argument('--emi', 
                        help="pre-installed emi id which to execute these tests against", default=None)
    parser.add_argument('--credpath', 
                        help="path to credentials", default=None)
    parser.add_argument('--zone', 
                        help="zone to use in this test, defaults to testing all zones", default=None)
    parser.add_argument('--password', 
                        help="password to use for machine root ssh access", default='foobar')
    parser.add_argument('--keypair', 
                        help="keypair to use when launching instances within the test", default=None)
    parser.add_argument('--group', 
                        help="group to use when launching instances within the test", default=None) 
    parser.add_argument('--config',
                       help='path to config file', default=None) 
    parser.add_argument('--vmtype',
                       help='vmtype to run this image with', default=None) 
    parser.add_argument('--rootpass',
                       help='root password this image is expected to be using', default=None) 
    parser.add_argument('--volcount',
                       help='number of volumes to use in test, default is 2', default=2) 
    parser.add_argument('--xof',
                       help='exit on fail boolean. Default is false, to continue testing', default=False) 
    parser.add_argument('--userlist', nargs='+', 
                        help="Login users expected to be found on this image", 
                        default= [])
    parser.add_argument('--tests', nargs='+', 
                        help="test cases to be executed", 
                        default= ['test_emi_suite'])
    
    args = parser.parse_args()
    
    '''
    Assign parsed arguments to this testcase globals
    '''
    if args.config is not None:
        #if file was not provided or is not found
        if not os.path.exists(args.config):
            print "Error: Mandatory Config File '"+str(args.config)+"' not found."
            parser.print_help()
            exit(1)
    elif args.credpath is None:
        print "Error either config file or credpath needs to be provided"
        exit(1)
    zone = args.zone
    config_file = args.config
    password = args.password
    credpath = args.credpath
    keypair = args.keypair
    group = args.group
    emi = args.emi
    userlist = args.userlist
    xof = args.xof
    volcount = args.volcount
    rootpass = args.rootpass
    vmtype = args.vmtype
    
    for test in args.tests:
        result = unittest.TextTestRunner(verbosity=2).run( emi_tests(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)

    
  