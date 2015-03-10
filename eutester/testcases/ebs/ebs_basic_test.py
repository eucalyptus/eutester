#!/usr/bin/env python

#
##########################
#                        #
#       Test Cases       #
#                        #
##########################
#
# [test_ebs_basic_test_suite]
#       Full suite of ebs related tests
#        Test Summary: 
#
#        -create a volume (do this first)
#        -run an instance (do this second, if this fails at least we know we could create a vol)
#        
#        Usage Tests: 
#        -negative -attempt to attach a volume to an instance in a separate cluster. 
#        -attach a single volume to an instance in the zones given, write random data and calc md5 of volumes
#        -negative:attempt to delete the attached instance, should fail
#        -negative:attempt to attach an in-use volume, should fail
#        -attach a 2nd volume to an instance, write random date to vol and calc md5 of volumes
#        -reboot instance
#        -verify both volumes are attached after reboot of instance. 
#        -detach 1st volume
#        -create snapshot of detached volume
#        -create snapshot of attached volume
#        -attempt to create a volume of each snapshot, if within a multi-cluster env do 1 in each cluster 
#        -attempt to attach each volume created from the previous snaps to an instance verify md5s
#        -'if' a bfebs instance was used, attempt to stop and detach volumes while in stopped state
#        -terminate all instances used in this test, verify any attached volumes return to available state
#        
#        Properties tests:
#        -create a volume of greater than prop size, should fail
#        -create a 2nd volume attempting to exceed the max aggregate size, should fail
#        
#        
#        Cleanup:
#        --remove all volumes, instance, and snapshots created during this test
#
#    @author: clarkmatthew


from ebstestsuite import EbsTestSuite

if __name__ == "__main__":
    # This script is now just a wrapper for ebstestsuite's basic test suite
    testcase= EbsTestSuite()
    testcase.clean_method = testcase.clean_created_resources
    testlist = testcase.ebs_basic_test_suite(run=False)

    ret = testcase.run_test_case_list(testlist,
                                      eof=testcase.args.exit_on_failure,
                                      clean_on_exit=testcase.args.clean_on_exit)
    print "ebs_basic_test exiting:("+str(ret)+")"
    exit(ret)

