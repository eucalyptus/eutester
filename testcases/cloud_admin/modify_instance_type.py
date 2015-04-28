#!/usr/bin/env python
#
# Description: Test the euca-modify-instance-type command works properly.

from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase

import subprocess
import sys
import os
import re
import random

class instance_type():  # mimicing a struct, I think this is the preferred way in python

    def __init__(self, name=None, cpus=None, mem=None, disk=None):
        self.name = name
        self.cpus = cpus
        self.mem = mem
        self.disk = disk

    def p(self):
        print ("Name: " + self.name + " cpu: " + str(self.cpus) + " mem: "
               + str(self.mem) + " disk: " + str(self.disk))

class InstanceTypeOps(EutesterTestCase):
    _known_types = []

    def __init__(self, credpath=None, region=None, config_file=None, password=None, emi=None, zone=None,
                  user_data=None, instance_user=None, **kwargs):

        self.setuptestcase()
        self.setup_parser()
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops(config_file=self.args.config_file,
                                  password=self.args.password,
                                  credpath=self.args.credpath)
        self.PopulateInstanceTypes()
        #print "Now printing _my_types after populating:"    # DEBUG
        #for i in InstanceTypeOps._known_types:
            #i.p()

    def clean_method(self):
        pass

    def DescribeInstanceTypes(self, item=None):
        print "in DescribeInstanceTypes function Running /usr/bin/euca-describe-instance-types"
        if item is None:
            cmd = ['/usr/bin/euca-describe-instance-types']
        else:
            cmd = ['/usr/bin/euca-describe-instance-types', item]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=4096)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            error = subprocess.CalledProcessError(retcode, 'euca-describe-instance-types')
            error.output = output
            raise error
        output.split("\n")
        return output

    def ModifyInstanceType(self, item=None):
        print "in ModifyInstanceType function Running /usr/bin/euca-modify-instance-type"
        if item is None:
            raise ValueError("Incorrect number of arguments, must pass cmd to ModifyInstanceType()")
        else:
            cmd = ['/usr/bin/euca-modify-instance-type']
            for i in item:
                #print "adding " + i + " to cmd list"    # DEBUG
                cmd.append(i)

        print "cmd is: "    # DEBUG
        print cmd[0:]    # DEBUG

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            error = subprocess.CalledProcessError(retcode, 'euca-modify-instance-type')
            error.output = output
            raise error
        output.split("\n")
        return output

    def PopulateInstanceTypes(self):
        print "Populating cluster Instance Types..."
        #process = subprocess.Popen('/usr/bin/euca-describe-instance-types', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=4096)
        #output, unused_err = process.communicate()
        #retcode = process.poll()
        #if retcode:
            #error = subprocess.CalledProcessError(retcode, 'euca-describe-instance-types')
            #error.output = output
            #raise error
        #output.split("\n")
        output = self.DescribeInstanceTypes()
        for row in output.splitlines():
            print "Got output: " + row    # DEBUG
            items = re.split("\s+", row)[1:5]
            if items[1] != "CPUs":   # ignore the heading line
                InstanceTypeOps._known_types.append(instance_type(name=items[0],cpus=int(items[1]),
                                                                  mem=int(items[2]),disk=int(items[3])))

    def Modify(self):
        """
        performs euca_modify_instance_type command
        """
        #print "random entry from _known_types is:"    # DEBUG
        #print(random.choice(InstanceTypeOps._known_types).p())  # print the random item chosen
        mychoice = random.choice(InstanceTypeOps._known_types)
        print "Randomly chose instance type \"" + mychoice.name + "\" from list, we will now "\
              + "execute \'euca-modify-instance-type\' command to double memory from \""\
              + str(mychoice.mem) + "\" to \"" + str((mychoice.mem*2)) + "\""
        myargs = ['--memory',
                str(mychoice.mem*2),
                mychoice.name]
        output = self.ModifyInstanceType(myargs)
        for row in output.splitlines():    # DEBUG
            print "Got output: " + row    # DEBUG

        # check the value is correct
        output = self.DescribeInstanceTypes(mychoice.name)
        for row in output.splitlines():
            print "Got output: " + row    # DEBUG
            items = re.split("\s+", row)[1:5]
            if items[1] != "CPUs":   # ignore the heading line
                print "memory is now: " + str(items[2])    # DEBUG
        # put it back together correctly
        newargs = ['--memory',
                str(mychoice.mem),
                mychoice.name]
        output = self.ModifyInstanceType(newargs)
        for row in output.splitlines():
            print "Got output: " + row    # DEBUG
        print "after fixing the memory:"    # DEBUG
        output = self.DescribeInstanceTypes(mychoice.name)
        for row in output.splitlines():
            print "Got output: " + row    # DEBUG
            items = re.split("\s+", row)[1:5]
            if items[1] != "CPUs":   # ignore the heading line
                print "memory is once again: " + str(items[2])    # DEBUG


if __name__ == "__main__":
    testcase = InstanceTypeOps()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["Modify"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)