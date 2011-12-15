#! ../share/python_lib/devel/bin/python
from eucaops import Eucaops
from optparse import OptionParser
import random
import os
import time

if __name__ == '__main__':
    ### Parse args
    parser = OptionParser()
    parser.add_option("-r","--runs", dest="runs", type="int",
                      help="How many times to run test", default=1) 
    parser.add_option("-m", "--max", action="store_true", dest="max",
                      help="Whether or not to launch the maximum number of instances")
    parser.add_option("-n", "--number", dest="number", type="int",
                      help="Number of instances of type to launch", default=1)
    parser.add_option("-c", "--config", type="string", dest="config",
                      help="Config file to use. Default: ../input/2b_tested.lst", default="../input/2b_tested.lst")
    parser.add_option("-t", "--type", type="string", dest="type",
                      help="Type of instance to launch Default: random", default="random")
    parser.add_option("-p", "--poll-count", type="int", dest="poll_count",
                      help="Number of 10s intervals to wait before giving up on an instance Default: 24", default=24)
    parser.add_option("-e", "--exit", action="store_true", dest="exit_on_fail",
                      help="Whether or not to stop the script after a failure")
    parser.add_option("-i", "--image", dest="exit_on_fail", type="string",
                      help="Whether or not to stop the script after a failure")
    (options, args) = parser.parse_args()
    ### LOAD OPTIONS INTO LOCAL VARS
    runs = options.runs
    max = options.max
    config = options.config
    type = options.type
    exit_on_fail = options.exit_on_fail
    number = options.number
    
    poll_count = options.poll_count
    tester = Eucaops( hostname="clc",password="foobar", config_file=config)
    tester.poll_count = poll_count
    image = tester.get_emi()
    config_filename = config.split("/")[-1]
    print "Config file name " + config_filename
    local = Eucaops ( credpath="eucarc-eucalyptus-admin", hostname="localhost", password="a1pine", config_file=config)
    try:    
        fail = 0
        success = 0
        while runs > 0:
            if type == "random":
                type = random.choice(["m1.small","c1.medium","m1.large","m1.xlarge","c1.xlarge"])
            if max == True:                
                available = tester.get_available_vms(type)
            else:
                available = number
                
            ### CREATE KEYPAIR AND GROUP
            group = tester.add_group()
            tester.authorize_group(group_name=group.name)
            keypair = tester.add_keypair(config_filename + "-" + str(time.time()))
            
            ### RUN INSTANCE AND WAIT FOR IT TO GO TO RUNNING
            print "Sending request for " + str(available) + " " + type + " VMs"
            reservation = tester.run_instance(image,keypair=keypair.name, min=available, max=available,type=type )
            keypath = os.getcwd() + "/" + config_filename + config + ".pem" 
            tester.sleep(20)
            ### SSH to instance
            for instance in reservation.instances:
               local.sys("scp " + keypath + " root@" + local.get_component_ip("clc") + ": ")
               if tester.found("ssh -i " + keypair.name + ".pem root@" + instance.ip_address + " mount", "/dev/sda2.*/mnt") == False:
                   tester.fail("Did not find ephemeral mounted in /dev/sda2")
            ### TEARDOWN INSTANCES, GROUP, KEYPAIR, AND ADDRESSES
            tester.terminate_instances(reservation)
            tester.delete_group(group)
            tester.delete_keypair(keypair)
            tester.release_address()
            local.sys("rm " + keypath)
            tester.sys("rm " + keypath)
            runs -= 1
            if tester.fail_count > 0: 
                fail += 1
                if exit_on_fail:
                    tester.fail_count= fail
                    tester.do_exit()
            else:
                success += 1
            tester.fail_count = 0
            print "\n*************************************************************"
            print "* Ran " + str( fail + success ) + " times"
            print "* Success: " + str(success) + " Failures: " + str(fail)
            print "*************************************************************\n"
        tester.fail_count= fail        
        tester.do_exit()
    except KeyboardInterrupt:
        tester.terminate_instances()
        tester.do_exit()