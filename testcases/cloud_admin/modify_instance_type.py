#!/usr/bin/env python
#
# Description: Test the euca-modify-instance-type command works properly.

from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase

import re
import random

class instance_type():  # mimicing a struct, I think this is the preferred way in python

    # shaon pointed out that I should be using Vm_Type instead of my own class
    # but can't figure that out right now - 4.28.2015 mbacchi
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

    def __init__(self, name="InstanceTypeOps", credpath=None, region=None, config_file=None, password=None, emi=None, zone=None,
                  user_data=None, instance_user=None, **kwargs):

        super(InstanceTypeOps, self).__init__(name=name)
        self.get_args()
        #self.show_args()
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        #self.show_args()
        self.setuptestcase()
        self.setup_parser()
        #self.get_args()
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

    def check_output_type(self, arg=None):
        """
        :param arg: argument must be a list or it will assert
        :return: assert if not list
        """
        assert type(arg) != None, "Output from self.sys() empty!"
        try:
            not isinstance(arg, basestring)
        except TypeError:
            AssertionError("Output from self.sys() should be list!")
        #print "Output type checks out correctly!"    # DEBUG

    def DescribeInstanceTypes(self, item=None):

        if item is None:
            cmd = "source " + self.tester.credpath + "/eucarc && /usr/bin/euca-describe-instance-types"
        else:
            cmd = "source " + self.tester.credpath + "/eucarc && /usr/bin/euca-describe-instance-types " + item

        print "in DescribeInstanceTypes function Running " + cmd

        output = self.tester.sys(cmd)

        self.check_output_type(output)

        return output

    def ModifyInstanceType(self, item=None):

        if item is None:
            raise ValueError("Incorrect number of arguments, must pass cmd to ModifyInstanceType()")
        else:
            cmd = "source " + self.tester.credpath + "/eucarc && /usr/bin/euca-modify-instance-type " + ' '.join(item)


        print "in ModifyInstanceType function Running " + cmd
        output = self.tester.sys(cmd)
        self.check_output_type(output)
        return output

    def PopulateInstanceTypes(self):
        print "Populating cluster Instance Types..."
        output = self.DescribeInstanceTypes()

        for row in output:
            #print "Got output: " + row    # DEBUG
            if "INSTANCETYPE" in row:
                items = re.split("\s+", row)[1:5]
                if items[1] != "CPUs":   # ignore the heading line
                    InstanceTypeOps._known_types.append(instance_type(name=items[0],cpus=int(items[1]),
                                                                  mem=int(items[2]),disk=int(items[3])))

    def Modify(self):
        """
        performs euca_modify_instance_type command
        """
        mychoice = random.choice(InstanceTypeOps._known_types)
        print "Randomly chose instance type \"" + mychoice.name + "\" from list, we will now "\
              + "execute \'euca-modify-instance-type\' command to double memory from \""\
              + str(mychoice.mem) + "\" to \"" + str((mychoice.mem*2)) + "\""
        myargs = ['--memory',
                str(mychoice.mem*2),
                mychoice.name]
        output = self.ModifyInstanceType(myargs)
        #for row in output:    # DEBUG
        #    print "Got output: " + row    # DEBUG

        # check the value is correct
        output = self.DescribeInstanceTypes(mychoice.name)
        for row in output:
            #print "Got output: " + row    # DEBUG
            if "INSTANCETYPE" in row:
                items = re.split("\s+", row)[1:5]
                if items[1] != "CPUs":   # ignore the heading line
                    #print "memory is now: " + str(items[2])    # DEBUG
                    assert mychoice.mem*2 != items[2], "New instance type " + mychoice.name + " memory was not set to 2x original value of " + mychoice.mem

        # put it back together correctly
        newargs = ['--memory',
                str(mychoice.mem),
                mychoice.name]
        output = self.ModifyInstanceType(newargs)
        #for row in output:    # DEBUG
        #    print "Got output: " + row    # DEBUG

        #print "after fixing the memory:"    # DEBUG
        output = self.DescribeInstanceTypes(mychoice.name)
        for row in output:
            #print "Got output: " + row    # DEBUG
            if "INSTANCETYPE" in row:
                items = re.split("\s+", row)[1:5]
                if items[1] != "CPUs":   # ignore the heading line
                    #print "memory is once again: " + str(items[2])    # DEBUG
                    assert mychoice.mem != items[2], "Instance type " + mychoice.name + " memory was not reset back to original value of " + mychoice.mem


if __name__ == "__main__":
    testcase = InstanceTypeOps()

    #### Adds argparse to testcase and adds some defaults args
    testcase.setup_parser()

    ### Get all cli arguments and any config arguments and merge them
    testcase.get_args()

    ### Instantiate an object of your test suite class using args found from above
    instancetypeops = testcase.do_with_args(InstanceTypeOps)

    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["Modify"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( instancetypeops.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)