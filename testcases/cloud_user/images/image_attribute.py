#!/usr/bin/python
#
# Author:       Vic and Graziano
# Description:  Eutester test case to reproduce bug 737335
#               Creates an instance of an image, and removes all permissions from the instance.
#               If there are still permissions after the command to remove all of them has executed, 
#               the test fails; otherwise, tries to run the image.
#    (https://bugs.launchpad.net/eucalyptus/+bug/737335)            
#

from eutester import Eutester
import argparse

if __name__ == '__main__':
    ### Parse args
    parser = argparse.ArgumentParser(description='Test for Eucalyptus Launchpad bug-737335')
    parser.add_argument("--credpath", dest="credpath",
                      help="The path where to find eucarc (default ~/.euca)", default="~/.euca") 
    parser.add_argument("--userId", dest="userId", 
                      help="userId to use to run test", default="admin") 
    args = parser.parse_args()
    
    # create Eutester object
    tester = Eutester( credpath=args.credpath )
    
    # find images owned by the user
    emi_list = tester.sys("euca-describe-images -o self | grep emi- | head -1 | awk '{print $2}'")
    
    if emi_list == []:
        tester.fail("Did not find any images owned by self")
        tester.do_exit()
    
    # grab an emi
    emi = emi_list[0]
    
    # reset permission
    tester.sys("euca-reset-image-attribute --launch-permission " + emi)
    
    # remove all permission
    tester.sys("euca-modify-image-attribute --launch-permission -r all " + emi)
    tester.sys("euca-modify-image-attribute --launch-permission -r " + args.userId + " " + emi)
    
    # check permission are empty
    if tester.sys("euca-describe-image-attribute -l " + emi) != []:
        tester.fail("Image still has attributes")
        tester.do_exit()
    
    # try to run it
    try:
        image = tester.get_emi(emi.rstrip())
        reservation = tester.run_instance(image)
        tester.fail("Was allowed to run instance")
        tester.terminate_instances(reservation)
    except Exception,e:
        tester.test_name("COMPLETED TEST SUCCESSFULLY!!!!")

    exit(0)
