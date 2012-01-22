#! ../share/python_lib/devel/bin/python
from eucaops import Eucaops
from optparse import OptionParser
import random
import os
import time
import smtplib
import string

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
    parser.add_option("--device",type="string", dest="device_prefix",
                      help="Device prefix expected to be found in running instance in /dev",  default="sd")
    parser.add_option("-i", "--image", dest="image", type="string",
                      help="Specific image to run", default="emi-")
    parser.add_option( "--prefix", dest="prefix", type="string",
                      help="Prefix to tack on to keypairs", default="load-test")
    parser.add_option( "--ebs", action="store_true", dest="ebs",
                      help="Run ebs attach/write/detach")
    parser.add_option("-z", "--zone", type="string", dest="zone",
                      help="AZ to run script against", default="PARTI00")
    parser.add_option("-u", "--user", type="string", dest="user",
                      help="User to run script as", default="admin")
    parser.add_option("-a", "--account", type="string", dest="account",
                      help="Account to run script as", default="eucalyptus")
    parser.add_option("--credpath", type="string", dest="credpath",
                      help="AZ to run script against", default=None)
    
    (options, args) = parser.parse_args()
    ### LOAD OPTIONS INTO LOCAL VARS

    got_creds = False
    while got_creds == False:      
        try:
            tester = Eucaops( credpath=options.credpath, hostname="clc", password="foobar",  config_file=options.config, boto_debug=0)
        except Exception,e:
            print str(e) 
            time.sleep(30)
            continue
        got_creds = True
    tester.poll_count = options.poll_count
    image = tester.get_emi(emi=options.image)
    config_filename = options.config.split("/")[-1]
    print "Config file name " + config_filename
    pwd =  os.getcwd()
    local = Eucaops ( config_file=options.config, credpath=options.credpath)
    current_reservation = None
    try:    
        fail = 0
        success = 0
        keypath = None
        keypair = None
        while options.runs > 0:
            try:
                ## identify type of instance to run
                if options.type == "random":
                    options.type = random.choice(["m1.small","c1.medium","m1.large","m1.xlarge","c1.xlarge"])
                
                ## identify number of instances to run
                if options.max == True:                
                    available = local.get_available_vms(options.type)
                else:
                    available = options.number
                
                ### Create group
                try:
                    group = tester.add_group(group_name=options.prefix + "-" + str(time.time()))
                except Exception,e :
                    print str(e)
                    continue
                ### Defaults to authorizing SSH, then run it again for authorizing icmp
                try:   
                    tester.authorize_group(group_name=group.name )
                    tester.authorize_group(group_name=group.name, port=-1, protocol="icmp" )
                except Exception,e :
                    print str(e)
                    group.delete()
                    continue
                ### Create keypair
                try:
                    keypair = tester.add_keypair(options.prefix + "-" + str(time.time()))
                except Exception,e :
                    print str(e)
                    continue
                              
                ### RUN INSTANCE AND WAIT FOR IT TO GO TO RUNNING
                tester.tee( "Sending request for " + str(available) + " " + options.type + " VMs")
                
                try:
                    reservation = tester.run_instance(image,keypair=keypair.name, group=group.name ,min=available, max=available,type=options.type )
                    current_reservation = reservation
                except Exception, e:
                    tester.fail("Failed launching instance")
                                  
                keypath = pwd + "/" + keypair.name + ".pem" 
                
                ### Some hypervisors will require a few seconds after "running" state for instance to boot
                tester.sleep(15)
                
                ### Log into each instance
                volumes = []
                for instance in reservation.instances:
                    if instance.state != "running":
                        continue
                    ### Ping the instance
                    local.sys("ping " + instance.ip_address + " -c 1")
                    
                    ###Create an ssh session to the instance using a eutester object
                    instance_ssh = Eucaops( hostname=instance.ip_address,  keypath=keypath, credpath=options.credpath, config_file=options.config)
                    
                    ### Ensure we know what device are on the instance before the attachment of a volume
                    before_attach = instance_ssh.sys("ls -1 /dev/ | grep " + options.device_prefix)
                    
                    ### Check that the ephemeral is available to the VM
                    if options.device_prefix + "a2\n" in before_attach:
                        print "Found ephemeral device"
                    else:
                        instance.terminate()
                        tester.fail("Did not find ephemeral mounted from /dev/" + options.device_prefix + "a2"+ " to /mnt on " + str(instance))
                        tester.tee("\n".join(tester.grep_euca_log(component="nc00",regex=instance.id)) + "\n".join(tester.grep_euca_log(regex=instance.id)) )
                        options.runs -= 1
                        continue 
                    
                    ### If the --ebs flag was passed to the script, attach a volume and verify it can be used
                    if options.ebs == True:
                        ## Create the volume
                        try:
                            volume = tester.create_volume(options.zone, size=1 )     
                        except Exception, e:
                            tester.fail("Something went wrong when creating the volume")
                            tester.tee( "Volume error\n".join(tester.grep_euca_log(regex=volume.id)) )
                            options.runs -= 1
                            continue
                        
                        ### Attach the volume (need to write a routine to validate the attachment)
                        try:
                            tester.tee("Attaching " + str(volume) + " as /dev/sdj")
                            volume.attach(instance.id, "/dev/sdj")
                        except Exception, e:
                            volume.delete()
                            tester.fail("Something went wrong when attaching " +  str(volume) +  " to " + str(instance) )
                            tester.tee( "Volume error\n".join(tester.grep_euca_log(regex=volume.id)) )
                            options.runs -= 1
                            continue
                        
                        tester.tee( "Sleeping and waiting for volume to attach fully to instances")
                        tester.sleep(20)
                        
                        ### Check what devices are found after the attachment
                        after_attach = instance_ssh.sys("ls -1 /dev/ | grep " + options.device_prefix)
                        
                        ### Use the eutester diff functionality to find the newly attached device
                        new_devices = tester.diff(after_attach, before_attach)
                        if new_devices == []:
                            tester.fail( str(volume) + " attached but not found on " + str(instance) )
                            tester.tee("Volume error\n".join(tester.grep_euca_log(regex=volume.id)) )
                            options.runs -= 1
                            continue
                        attached_block_dev =  new_devices[0].strip()
                        
                        ### Add volume to list of volumes for cleanup
                        volumes.append(volume)
                        
                        ### Make a file system on the volume and mount it 
                        tester.tee( "Found new device attached to instance " + str(instance) + ": " + attached_block_dev )
                        instance_ssh.sys("mkfs.ext3 -F /dev/" + attached_block_dev )
                        instance_ssh.sys("mkdir /mnt/device" )
                        instance_ssh.sys("mount /dev/" +  attached_block_dev  + " /mnt/device")
                        
                        ### Make sure the volume shows as mounted
                        if instance_ssh.found("df", attached_block_dev + ".*/mnt/device") == False:
                            tester.fail("Could not find " +  attached_block_dev +" in output of df")
                            tester.tee("Volume error\n".join(tester.grep_euca_log(regex=volume.id)) )
                        
                        ### Unmount the volume
                        if instance_ssh.sys("umount /mnt/device") != []:
                            tester.fail("Failure unmounting volume")
                            
                ### TEARDOWN INSTANCES, VOLUMES GROUP, KEYPAIR, AND ADDRESSES 
                for vol in volumes:
                    try:
                        tester.detach_volume(vol)
                    except Exception, e:
                        print str(e)
                        tester.fail("Something went wrong when attaching " +  str(volume) +  " to " + str(instance) )
                        tester.tee( "Volume log:"+  "\n".join(tester.grep_euca_log(regex=volume.id)) )
                        options.runs -= 1
                        continue
                    
                    try:
                        tester.delete_volume(vol)
                    except Exception, e:
                        tester.fail("Something went wrong when attaching " +  str(volume) +  " to " + str(instance) )
                        #tester.tee( "\n".join(tester.test_report()) + "\nException:\n" + str(e) + "\n".join(tester.grep_euca_log(regex=volume.id))   )
                        tester.tee( "Volume log:"+  "\n".join(tester.grep_euca_log(regex=volume.id)) )
                        options.runs -= 1
                        continue   
                                    
                tester.terminate_instances(reservation)
                tester.delete_group(group)
                tester.delete_keypair(keypair)
                
                local.sys("rm " +  keypath  )

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
                tester.tee( "*************************************************************")
                tester.tee( "* Ran " + str( fail + success ) + " times")
                tester.tee( "* Success: " + str(success) + " Failures: " + str(fail))
                tester.tee( "*************************************************************")            
            ### Catches any unexpected exceptions 
            except Exception,e:
                msg = '\nPassed: ' +  str(success) + "\nFailed: " + str(fail) + "\nUncaught Exceptions was:\n"+ str(e) + "\n" 
                tester.tee(msg)
                if keypath != None:
                    local.sys("rm " +  keypath  )
                if keypair != None:
                    tester.sys("rm " +  keypair.name + ".pem")
                tester.sleep(30)
    ### If the script catches a Ctrl+c kill it immediately for debugging purposes           
    except KeyboardInterrupt:
        exit(1)
    