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
    parser.add_option("-i", "--image", dest="image", type="string",
                      help="Specific image to run", default="emi-")
    parser.add_option( "--prefix", dest="prefix", type="string",
                      help="Prefix to tack on to keypairs", default="keypair")
    parser.add_option( "--ebs", action="store_true", dest="ebs",
                      help="Run ebs attach/write/detach")
    parser.add_option("-z", "--zone", type="string", dest="zone",
                      help="AZ to run script against", default="PARTI00")
    parser.add_option("-u", "--user", type="string", dest="user",
                      help="AZ to run script against", default="admin")
    parser.add_option("-a", "--account", type="string", dest="account",
                      help="AZ to run script against", default="eucalyptus")
    
    (options, args) = parser.parse_args()
    ### LOAD OPTIONS INTO LOCAL VARS
    runs = options.runs
    max = options.max
    config = options.config
    type = options.type
    exit_on_fail = options.exit_on_fail
    number = options.number
    prefix = options.prefix
    image = options.image
    ebs = options.ebs
    zone = options.zone
    user = options.user
    account = options.account
    
    poll_count = options.poll_count
    tester = Eucaops( hostname="clc",password="foobar", user=user, account=account,config_file=config)
    tester.poll_count = poll_count
    image = tester.get_emi(emi=image)
    config_filename = config.split("/")[-1]
    print "Config file name " + config_filename
    print "Running script as " + user + "@" + account
    local = Eucaops ( credpath="eucarc-" + account + "-" + user, hostname="localhost", password="a1pine", config_file=config)
    current_reservation = None
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
            group = tester.add_group(group_name=prefix + "-" + str(time.time()))
            tester.authorize_group(group_name=group.name )
            keypair = tester.add_keypair(prefix + "-" + str(time.time()))
            
            ### RUN INSTANCE AND WAIT FOR IT TO GO TO RUNNING
            print "Sending request for " + str(available) + " " + type + " VMs"
            reservation = tester.run_instance(image,keypair=keypair.name, min=available, max=available,type=type )
            current_reservation = reservation
            keypath = os.getcwd() + "/" + keypair.name + ".pem" 
            tester.sleep(20)
            ### SSH to instance
            volumes = []
            for instance in reservation.instances:        
                local.sys("scp " + keypath + " root@" + local.get_component_ip("clc") + ": ")
                ssh_prefix = "ssh -i " + keypair.name + ".pem root@" + instance.ip_address + " "
                before_attach = tester.sys(ssh_prefix + "ls -1 /dev/")
                if tester.found(ssh_prefix + "mount", "/dev/sda2.*/mnt") == False:
                   tester.fail("Did not find ephemeral mounted in /dev/sda2")
                else:
                    if ebs == True:
                        try:
                            volume = tester.create_volume(zone, size=10)     
                        except Exception, e:
                            tester.fail("Something went wrong when creating the volume")
                            print e
                            continue
                        try:
                            volume.attach(instance.id, "/dev/sdj")
                        except Exception, e:
                            tester.fail("Something went wrong when attaching the volume to " + str(instance) )
                            volume.delete()
                            print e
                            continue
                        
                        print "Sleeping and waiting for volume to attach fully to instances"
                        tester.sleep(10)
                        after_attach = tester.sys(ssh_prefix +  "ls -1 /dev/")
                        new_devices = tester.diff(after_attach, before_attach)
                        attached_block_dev =  new_devices[0].strip()
                        if new_devices == []:
                            tester.fail("Volume attached but not found on " + str(instance) )
                            volume.delete()
                            continue
                        volumes.append(volume)
                        print "Found new device attached to instance " + str(instance) + ": " + attached_block_dev
                        tester.sys(ssh_prefix +  "mkfs.ext3 -F /dev/" + attached_block_dev )
                        tester.sys(ssh_prefix +  "mkdir /mnt/device" )
                        tester.sys(ssh_prefix +  "mount /dev/" +  attached_block_dev  + " /mnt/device")
                        if tester.found(ssh_prefix +  "df", attached_block_dev + ".*/mnt/device") == False:
                            tester.fail("Could not find block device in output of df")
            ### TEARDOWN INSTANCES, VOLUMES GROUP, KEYPAIR, AND ADDRESSES
            tester.terminate_instances(reservation)
            for vol in volumes:
                tester.delete_volume(vol)
            tester.delete_group(group)
            tester.delete_keypair(keypair)
            tester.release_address()
            local.sys("rm " +  keypair.name + ".pem")
            tester.sys("rm " +  keypair.name + ".pem")
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
        tester.terminate_instances(current_reservation)
        tester.do_exit()