#!/Users/hspencer/Desktop/eutester-dev/bin/python
#
# Description:  This case was developed to test the integrity of iptables upon
#               deletion of security groups. Based up the arguments passed, the test 
#               creates at least 3 security groups and launches an instance for each one.
#               Once each instance has been launched, a snapshot of iptables is taken.
#               Then each instance is terminated, followed by each security group being terminated.
#		Another snapshot of iptables is done.  There is a comparison of iptables. 
#		The results are logged. 
#

from eucaops import Eucaops
import argparse
import random
import os
import time
import string

if __name__ == '__main__':
    ### Parse args
    parser = argparse.ArgumentParser(prog="iptables_security_group_test.py", version="Test Case [iptables_security_group_test.py] Version 0.1", description='Run an iterative test of operations on a cloud to test integrity of iptables state upon deletion of security groups.  For more information, please refer to https://github.com/hspencer77/eutester/wiki/iptables_security_group_test')
    parser.add_argument("-r","--runs", dest="runs", type=int,
                      help="How many times to run test", default=1) 
    parser.add_argument("-n", "--number", dest="number", type=int,
                      help="Number of security groups to create", default=3)
    parser.add_argument("-e", "--exit", action="store_true", dest="exit_on_fail",
                      help="Whether or not to stop the script after a failure")
    parser.add_argument("-i", "--image", dest="image", 
                      help="Specific image to run", default=None)
    parser.add_argument("-t", "--type",  dest="type",
                      help="Type of instance to launch Default: random", default="random")
    parser.add_argument( "--prefix", dest="prefix", 
                      help="Prefix to tack on to keypairs", default="iptables-secgrp-test")
    parser.add_argument("-z", "--zone",  dest="zone",
                      help="AZ to run script against", default="PARTI00")
    parser.add_argument("-u", "--user",  dest="user",
                      help="User to run script as", default="admin")
    parser.add_argument("-a", "--account",  dest="account",
                      help="Account to run script as", default="eucalyptus")
    parser.add_argument("-U", "--username",  dest="username",
                      help="User account on physical CC machine", default="root")
    parser.add_argument("-P", "--password",  dest="password",
                      help="Password for user account on physical CC machine", default=None)
    parser.add_argument("--config_file",  dest="config_file",
                      help="Cloud config of AZ", default=None)
    parser.add_argument("--credpath",  dest="credpath",
                      help="AZ to run script against", default=None)
    
    options = parser.parse_args()
    ### LOAD OPTIONS INTO LOCAL VARS

    got_creds = False
    while got_creds == False:      
        try:
	    if options.config_file:
            	tester = Eucaops(config_file=options.config_file, password=options.password, boto_debug=0)
	    elif options.credpath:
            	tester = Eucaops(credpath=options.credpath, password=options.password, boto_debug=0)
            else:
		print "\tNeed to pass either --credpath or --config_file option. Try --help for more information"	
		exit(1)
        except Exception,e:
            print str(e) 
            time.sleep(30)
            continue
        got_creds = True
    
    if (options.image):
    	image = tester.get_emi(emi=options.image)
    else:
	image = tester.get_emi(root_device_type="instance-store")

    pwd =  os.getcwd()
    try:    
        fail = 0
        success = 0
        keypath = None
        keypair = None
        while options.runs > 0:
            ## identify type of instance to run
            if options.type == "random":
                options.type = random.choice(["m1.small","c1.medium","m1.large","m1.xlarge","c1.xlarge"])
            
            ## identify number of instances to run (i.e. number of security groups)
            num_vms = tester.get_available_vms(options.type)

	    if num_vms > options.number:
		available = options.number
	    else:
		options.type = "m1.small"
		avail_vms = tester.get_available_vms(options.type)
		if avail_vms < options.number:
			tester.fail("Not enough m1.small vm types to run test")
		else:
            		available = options.number

            ### Create keypair
            try:
                keypair = tester.add_keypair(options.prefix + "-" + str(time.time()))
            except Exception,e :
                print str(e)
                continue

            keypath = pwd + "/" + keypair.name + ".pem"
            
            ### Create security groups
	    security_groups = []
	    while available > 0:
            	try:
                	sec_group = tester.add_group(group_name=options.prefix + "-" + str(time.time()))
            	except Exception,e :
               	 	print str(e)
                	continue
            	### Defaults to authorizing SSH, then run it again for authorizing icmp
            	try:   
                	tester.authorize_group(sec_group)
                	tester.authorize_group(sec_group, port=-1, protocol="icmp" )
			security_groups.append(sec_group)
            	except Exception,e :
                	print str(e)
                	sec_group.delete()
                	continue
            
            	try:
                	reservation = tester.run_instance(image,keypair=keypair.name, group=sec_group.name ,type=options.type)
            	except Exception, e:
                	tester.fail("Failed launching instance")

            	### Some hypervisors will require a few seconds after "running" state for instance to boot
            	tester.sleep(15)
            
            	### Log into each instance
            	for instance in reservation.instances:
                	## Update instance info
                	instance.update()
                
               	if instance.state != "running":
                    tester.fail("Instance did not go to running state")
                    available -= 1
                    continue
                
                if instance.public_dns_name == instance.private_ip_address:
                    tester.fail("Did not get a private IP")
                    available -= 1
                    continue
               
		available -= 1 
	    #
	    # Take snapshot of iptables on CC
	    #

	    # Loop through and terminate instances                
	    total_reservations = tester.ec2.get_all_instances()
	    for reservation in total_reservations:
            	tester.terminate_instances(reservation)

	    # Loop through and delete security groups                
	    for group in security_groups: 
            	tester.delete_group(group)

	    #
	    # Take snapshot of iptables on CC
	    #


            tester.delete_keypair(keypair)
	    os.remove(keypath)

            options.runs -= 1
            if tester.fail_count > 0: 
                fail += 1
                tester.fail_log = []
                if options.exit_on_fail:
                    tester.fail_count= fail
                    tester.do_exit()
            else:
                success += 1
            tester.fail_count = 0     
            tester.running_log = []
            #tester.tee( "*************************************************************")
            #tester.tee( "* Ran " + str( fail + success ) + " times")
            #tester.tee( "* Success: " + str(success) + " Failures: " + str(fail))
            #tester.tee( "*************************************************************")                      
    except KeyboardInterrupt:
        exit(1)
    
