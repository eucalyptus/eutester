#!/usr/bin/env python

#
##########################
#                        #
#       Test Cases       #
#                        #
##########################
#
#       Attempt to test volume churn in a multi-node env. Attempts multi-node usage by creating/using 
#        a number of instances equal to the node count. 
#        Test Summary: 
#        
#        Usage Tests: 
#
#        Cleanup:
#        --remove all volumes, instance, and snapshots created during this test
#
#    @author: clarkmatthew

import unittest
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import EutesterTestResult
from ebstestsuite import EbsTestSuite
import argparse
import os



if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch

    testcase= EutesterTestCase(name='multi_node_churn')    
    testcase.setup_parser(description="Attempts to test and provide info on focused areas related to Eucalyptus EBS related functionality.", 
                          testlist=False)
    testcase.parser.add_argument('--count', type=int, help='Number of times to run attach/detach churn',default=10)
    testcase.parser.add_argument('--nodecount', type=int, help='Number of nodes in env',default=2)

    testcase.get_args()
    ebstestsuite= testcase.do_with_args(EbsTestSuite)
    #testcase.clean_method = ebstestsuite.clean_created_resources
    testlist = ebstestsuite.test_multi_node(run=False, 
                                            count=int(testcase.args.count),
                                            nodecount=int(testcase.args.nodecount))
    ret = testcase.run_test_case_list(testlist)
    print "mutli node test exiting:("+str(ret)+")"
    exit(ret)

    
  
