#!/usr/bin/python
#
#
# Description:  This script encompasses test cases/modules concerning stressing EBS specific actions and
#               features for Eucalyptus.
#
##########################
#                        #
#       Test Cases       #
#                        #
##########################
#
# [EbsStress]
#
#               This case was developed to test the integrity of the following:
#                   * state of tgtd (Open iSCSI)
#                   * disk state of SC machine
#                   * PSQL database state of eucalyptus_storage table:
#                           - iscsivolumeinfo relation
#                           - volumes relation
#                           - iscsimetadata relation
#                           - storage_stats_info
#                   * PSQL database state of eucalyptus_cloud table:
#                           - metadata_volumes
#                   * Loopback device integrity
#                   * LVM integrity
#               after stressing the SC with asynchronous volume create/delete calls.
#
# [GenerateVolumesLoad]
#
#               This case was developed to test the creation of volumes in a serial manner.
#               This case is a subcase of EbsStress.
# 
# [GenerateCloudStatistics] 
#               
#               This case was developed to provide statistical output of EBS related information
#               for the cloud.  Currently, it displays the following infromation:
#                   * number of creating, available, deleting, deleted, and failed volumes
#                   * PSQL database state of eucalyptus_storage table:
#                           - iscsivolumeinfo relation
#                           - volumes relation
#                           - iscsimetadata relation
#                           - storage_stats_info
#                   * PSQL database state of eucalyptus_cloud table:
#                           - metadata_volumes       

import unittest
import time
from eucaops import Eucaops
from eutester import xmlrunner
import os
import re
import random
import argparse
import string
import sys
import pprint
import datetime

class LoadGenerator(unittest.TestCase):
    def setUp(self):
        # Setup basic eutester object
        if options.config_file:
            self.tester = Eucaops(config_file=options.config_file, password=options.clc_password)
        else:
            print "\tNeed to pass --config_file option. Try --help for more information\n"  
            exit(1)

        ### Grab zone for volume tests
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name
        self.volumes = []
        self.statuses = []

    def tearDown(self):
        """
        If extra debugging is set, print additional CLC and SC information
        """
        if options.print_debug is True:
            self.get_clc_stats()
            self.get_sc_stats()
            """
            Print the results of volumes created and total volumes of cloud
            """
            self.current_ebs_reporting()
            """
            Print all the volumes' statuses for the entire cloud
            """
            self.overall_ebs_reporting()
            """
            Display information in eucalyptus_storage,eucalyptus_cloud tables related to EBS -
                * eucalyptus_storage relations: iscsivolumeinfo, iscsimetadata, volumes, storage_stats_info
                * eucalyptus_cloud relations: metadata_volumes
            """
            self.iscivolumeinfo_db_dump()
            self.iscsimetadata_db_dump()
            self.volumes_db_dump()
            self.cloudmetadata_db_dump()
            self.storagestats_db_dump()

        """
        Now destroy volumes created and reached available state from test
        """
        for vol in self.volumes:
            if vol.status == "available":
                self.tester.delete_volume(vol)
        self.volumes = None
        self.statuses = None
        self.tester = None
        
    def current_ebs_reporting(self):
        """
        Print the results of volumes created and total volumes of cloud
        """
        found_creating = self.statuses.count("creating")
        found_available = self.statuses.count("available")
        found_deleting = self.statuses.count("deleting")
        found_deleted = self.statuses.count("deleted")
        found_failed = self.statuses.count("failed")

        self.tester.debug("##########################################\n")
        self.tester.debug("\t**** Results of Finished Test ****\n")
        self.tester.debug("\t" + str(found_creating) + " Volumes in CREATING state.\n")
        self.tester.debug("\t" + str(found_available) + " Volumes in AVAILABLE state.\n")
        self.tester.debug("\t" + str(found_deleting) + " Volumes in DELETING state.\n")
        self.tester.debug("\t" + str(found_deleted) + " Volumes in DELETED state.\n")
        self.tester.debug("\t" + str(found_failed) + " Volumes in FAILED state.\n")
        self.tester.debug("##########################################\n")

        found_creating = None
        found_available = None
        found_deleting = None
        found_deleted = None
        found_failed = None

    def overall_ebs_reporting(self):
        """
        Print all the volumes' statuses for the entire cloud
        """
        volumes = self.tester.get_volumes()
        statuses = []
        for master_vol in volumes:
            statuses.append(master_vol.status)

        overall_creating = statuses.count("creating")
        overall_available = statuses.count("available")
        overall_deleting = statuses.count("deleting")
        overall_deleted = statuses.count("deleted")
        overall_failed = statuses.count("failed")

        """
        Grab cloud property for volume location to get stats of files.
        """
        volumes_dir = ""
        for machine in self.tester.get_component_machines("clc"):
            if volumes_dir == "":
                volumes_dir = (machine.sys("source " + self.tester.credpath + "/eucarc && euca-describe-properties | grep volumesdir | awk '{print $3}'"))

        overall_ebs_size = len(volumes)
        ebs_filesystem_size = ""
        for machine in self.tester.get_component_machines("sc"):
            ebs_filesystem_size = (machine.sys("du -sh " + volumes_dir[0]))

        self.tester.debug("##########################################\n")
        self.tester.debug("\t**** Results of Current Volumes on Cloud ****\n")
        self.tester.debug("\t" + str(overall_creating) + " Volumes in CREATING state.\n")
        self.tester.debug("\t" + str(overall_available) + " Volumes in AVAILABLE state.\n")
        self.tester.debug("\t" + str(overall_deleting) + " Volumes in DELETING state.\n")
        self.tester.debug("\t" + str(overall_deleted) + " Volumes in DELETED state.\n")
        self.tester.debug("\t" + str(overall_failed) + " Volumes in FAILED state.\n")
        self.tester.debug("==========================================\n")
        self.tester.debug("Sum of All EBS Volume Sizes (in GBs): " + str(overall_ebs_size) + "\n")
        self.tester.debug("Disk Space Used under Cloud defined Storage Directory [ " + volumes_dir[0] + " ]: " + ebs_filesystem_size[0] + "\n")
        self.tester.debug("##########################################\n")

        statuses = None
        volumes = None
        ebs_filesystem_size = None
        overall_ebs_size = None
        volumes_dir = None
        overall_creating = None
        overall_available = None
        overall_deleting = None
        overall_deleted = None
        overall_failed = None

    def iscivolumeinfo_db_dump(self):
        """
        Print contents of iscsivolumeinfo relation in eucalyptus_storage table
        """
        now = datetime.datetime.now()
        iscsivolinfo_file = "~/iscsivolinfo_file-" + str(now.microsecond) + ".txt"
        db_dump = ""
        for machine in self.tester.get_component_machines("clc"):
            machine.sys("psql -p 8777 -x -e -t -S -h ${EUCALYPTUS}/var/lib/eucalyptus/db/data eucalyptus_storage -c 'select * from iscsivolumeinfo' -o " + iscsivolinfo_file)
            db_dump = (machine.sys("cat " + iscsivolinfo_file))
            machine.sys("rm -rf " + iscsivolinfo_file)

        self.tester.debug("##########################################\n")
        self.tester.debug("\t**** Content of iscsivolumeinfo relation ****\n")
        for content in db_dump:
            self.tester.debug(content + "\n")
        self.tester.debug("##########################################\n")

        now = None
        iscsivolinfo_file = None
        db_dump = None
            
    def iscsimetadata_db_dump(self):
        """
        Print contents of iscsimetadata relation in eucalyptus_storage table
        """
        now = datetime.datetime.now()
        iscsimetadata_file = "~/iscsimetadata_file-" + str(now.microsecond) + ".txt"
        db_dump = ""
        for machine in self.tester.get_component_machines("clc"):
            machine.sys("psql -p 8777 -x -e -t -S -h ${EUCALYPTUS}/var/lib/eucalyptus/db/data eucalyptus_storage -c 'select * from iscsimetadata' -o " + iscsimetadata_file)
            db_dump = (machine.sys("cat " + iscsimetadata_file))
            machine.sys("rm -rf " + iscsimetadata_file)

        self.tester.debug("##########################################\n")
        self.tester.debug("\t**** Content of iscsimetadata relation ****\n")
        for content in db_dump:
            self.tester.debug(content + "\n")
        self.tester.debug("##########################################\n")

        now = None
        iscsimetadata_file= None
        db_dump = None

    def volumes_db_dump(self):
        """
        Print contents of volumes relation in eucalyptus_storage table
        """
        now = datetime.datetime.now()
        volumes_file = "~/volumes_file-" + str(now.microsecond) + ".txt"
        db_dump = ""
        for machine in self.tester.get_component_machines("clc"):
            machine.sys("psql -p 8777 -x -e -t -S -h ${EUCALYPTUS}/var/lib/eucalyptus/db/data eucalyptus_storage -c 'select * from volumes' -o " + volumes_file)
            db_dump = (machine.sys("cat " + volumes_file))
            machine.sys("rm -rf " + volumes_file)

        self.tester.debug("##########################################\n")
        self.tester.debug("\t**** Content of volume relation ****\n")
        for content in db_dump:
            self.tester.debug(content + "\n")
        self.tester.debug("##########################################\n")

        now = None
        volumes_file= None
        db_dump = None

    def cloudmetadata_db_dump(self):
        """
        Print contents of metadata_volumes relation in eucalyptus_cloud table
        """
        now = datetime.datetime.now()
        cloudmetadata_file = "~/cloudmetadata_file-" + str(now.microsecond) + ".txt"
        db_dump = ""
        for machine in self.tester.get_component_machines("clc"):
            machine.sys("psql -p 8777 -x -e -t -S -h ${EUCALYPTUS}/var/lib/eucalyptus/db/data eucalyptus_cloud -c 'select * from metadata_volumes' -o " + cloudmetadata_file)
            db_dump = (machine.sys("cat " + cloudmetadata_file))
            machine.sys("rm -rf " + cloudmetadata_file)

        self.tester.debug("##########################################\n")
        self.tester.debug("\t**** Content of metadata_volumes relation ****\n")
        for content in db_dump:
            self.tester.debug(content + "\n")
        self.tester.debug("##########################################\n")

        now = None
        cloudmetadata_file= None
        db_dump = None

    def storagestats_db_dump(self):
        """
        Print contents of storage_stats_info relation in eucalyptus_storage table
        """
        now = datetime.datetime.now()
        storagestats_file = "~/storagestats_file-" + str(now.microsecond) + ".txt"
        db_dump = ""
        for machine in self.tester.get_component_machines("clc"):
            machine.sys("psql -p 8777 -x -e -t -S -h ${EUCALYPTUS}/var/lib/eucalyptus/db/data eucalyptus_storage -c 'select * from storage_stats_info' -o " + storagestats_file)
            db_dump = (machine.sys("cat " + storagestats_file))
            machine.sys("rm -rf " + storagestats_file)

        self.tester.debug("##########################################\n")
        self.tester.debug("\t**** Content of storage_stats_info relation ****\n")
        for content in db_dump:
            self.tester.debug(content + "\n")
        self.tester.debug("##########################################\n")

        now = None
        storagestats_file= None
        db_dump = None

    def run_command_list(self,machine, list):
        for command in list:
            machine.sys(command)

    def get_clc_stats(self):

        basic_commands = ['df -B M',
                          'ps aux',
                          'free',
                          'uptime']

        clc_commands = ['euca-describe-properties | grep volume']

        clc_status = clc_commands + basic_commands
        for machine in self.tester.get_component_machines("clc"):
            for command in clc_status:
                machine.sys("source " + self.tester.credpath + "/eucarc && " + command)

    def get_sc_stats(self):

        basic_commands = ['df -B M',
                          'ps aux',
                          'free',
                          'uptime']
        
        """
        Grab cloud property for volume location to get stats of files.
        """
        volumes_dir = ""
        for machine in self.tester.get_component_machines("clc"):
            if volumes_dir == "":
                volumes_dir = (machine.sys("source " + self.tester.credpath + "/eucarc && euca-describe-properties | grep volumesdir | awk '{print $3}'"))

        sc_commands = ['tgtadm --lld iscsi --op show --mode account',
                       'tgtadm --lld iscsi --op show --mode target',
                       'du -sh ' + volumes_dir[0],
                       'lvdisplay | grep "/dev/vg-"',
                       'vgdisplay',
                       'pvdisplay',
                       'losetup -a | grep ' + volumes_dir[0] + ' | wc -l',
                       'ls -l ' + volumes_dir[0]]

        sc_status = basic_commands + sc_commands
        for machine in self.tester.get_component_machines("sc"):
            self.run_command_list(machine, sc_status)

    def GenerateVolumesLoad(self):
        """
        Grab EBS Timeout property of Cloud
        """
        ebs_timeout = ""
        for machine in self.tester.get_component_machines("clc"):
            if ebs_timeout == "":
                ebs_timeout = (machine.sys("source " + self.tester.credpath + "/eucarc && euca-describe-properties | grep ebs_volume_creation_timeout | awk '{print $3}'"))
        
        """
        Create volumes in series
        """
        for i in xrange(options.number_of_vol):
            volume = self.tester.create_volume(self.zone)
            if volume is not None:
                self.volumes.append(volume)
                self.statuses.append(volume.status)

        """
        Sleep the EBS Timeout property; only have to call it once
        """
        self.tester.debug("###\n")
        self.tester.debug("###\tWaiting till EBS Timeout is reached; sleep for " + ebs_timeout[0] + " seconds.\n")
        self.tester.debug("###\n")
        self.tester.sleep(float(ebs_timeout[0]))

    def GenerateCloudStatistics(self):
        """
        Grab status of all volumes on cloud, along with database information
        """
        self.overall_ebs_reporting()
        """
        Display information in eucalyptus_storage,eucalyptus_cloud tables related to EBS -
            * eucalyptus_storage relations: iscsivolumeinfo, iscsimetadata, volumes, storage_stats_info
            * eucalyptus_cloud relations: metadata_volumes
        """
        self.iscivolumeinfo_db_dump()
        self.iscsimetadata_db_dump()
        self.volumes_db_dump()
        self.cloudmetadata_db_dump()
        self.storagestats_db_dump()
        
    def EbsStress(self, testcase="GenerateVolumesLoad"):
        """
        Generate volume load; For each thread created - options.number_of_threads
         - options.number_of_vol will be created
        """
        from multiprocessing import Process
        from multiprocessing import Queue

        ### Increase time to by step seconds on each iteration
        step = 10

        """
        If extra debugging is set, print additional CLC and SC information
        """
        if options.print_debug is True:
            self.get_clc_stats()
            self.get_sc_stats()
        
        thread_pool = []
        queue_pool = []

        ## Start asynchronous activity
        ## Run GenerateVolumesLoad testcase 5s apart
        for i in xrange(options.number_of_threads):
            q = Queue()
            queue_pool.append(q)
            p = Process(target=self.run_testcase_thread, args=(q, step * i,testcase))
            thread_pool.append(p)
            self.tester.debug("Starting Thread " + str(i) +" in " + str(step * i))
            p.start()

        fail_count = 0
        ### Block until the script returns a result
        for queue in queue_pool:
            test_result = queue.get(True)
            self.tester.debug("Got Result: " + str(test_result) )
            fail_count += test_result

        for thread in thread_pool:
            thread.join()
        
        if fail_count > 0:
            self.tester.critical("Failure detected in one of the " + str(fail_count)  + " GenerateVolumesLoad tests")

        self.tester.debug("Successfully completed EbsStress test")
        
    def run_testcase_thread(self, queue,delay = 20, name="EbsStress"):
        ### Thread that runs a testcase (function) and returns its pass or fail result
        self.tester.sleep(delay)
        try:
            result = unittest.TextTestRunner(verbosity=2).run(LoadGenerator(name))
        except Exception, e:
            queue.put(1)
            raise e
        if result.wasSuccessful():
            self.tester.debug("Passed test: " + name)
            queue.put(0)
            return False
        else:
            self.tester.debug("Failed test: " + name)
            queue.put(1)
            return True

def get_options():
    ### Parse args
    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(prog="ebs_stress.py",
        version="Test Case [ebs_stress.py] Version 0.0.1",
        description='Run stress testing operations on a cloud to test Eucalyptus Storage Controller \
        functionality. This also tests disk, database, lvm, and loopback device integrity before and \
        after the test has been executed.')
    parser.add_argument("-U", "--username",  dest="username",
        help="User account on physical CC and CLC machine", default="root")
    parser.add_argument("--clc-password",  dest="clc_password",
        help="Password for user account on physical CLC machine", default=None)
    parser.add_argument("--config_file",  dest="config_file",
        help="Cloud config of AZ", default=None)
    parser.add_argument("-n", "--number", dest="number_of_vol", type=int,
        help="Number of volumes to create", default=10)
    parser.add_argument("-t", "--thread_number", dest="number_of_threads", type=int,
        help="Number of threads to create for concurrent testing", default=2)
    parser.add_argument("-d", "--debug", action="store_true", dest="print_debug",
        help="Whether or not to print debugging")
    parser.add_argument('--xml', action="store_true", default=False)
    parser.add_argument('--tests', nargs='+', default= ["EbsStress","GenerateCloudStatistics"])
    parser.add_argument('unittest_args', nargs='*')

    ## Grab arguments passed via commandline
    options = parser.parse_args() 
    sys.argv[1:] = options.unittest_args
    return options

if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch
    options = get_options()
    for test in options.tests:
        if options.xml:
            file = open("test-" + test + "result.xml", "w")
            result = xmlrunner.XMLTestRunner(file).run(LoadGenerator(test))
        else:
            result = unittest.TextTestRunner(verbosity=2).run(LoadGenerator(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)
