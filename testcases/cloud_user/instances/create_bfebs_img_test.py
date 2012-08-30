
#
# Description:  Creates an image instance based on the image argument passed in. Then 
#               attempts to download a remote image and store it on an attached volume.
#               A snapshot is then created from the splatted volume that the remote image
#               was written to. Lastly the emi of the snapshot is registered. Upon completion,
#               the volume is deleted and the instance is terminated. 
#
#               bfebs = Amazon Elastic Block Store (http://aws.amazon.com/ebs/)
#

from eucaops import Eucaops
from optparse import OptionParser
import os, re
import time
import httplib
from eutester import euinstance

def pmsg(msg):
    print "\n---------------PROGRESS MESSAGE----------\n"
    print   msg
    print "\n-----------------------------------------\n"
    
    
if __name__ == '__main__':
    
    ### Parse command line arguments
    parser = OptionParser()
    parser.add_option("--url", dest="url", type="string",
                      help="How many times to run test", default=None)    
    
    parser.add_option("-i", "--i", dest="img", type="string",
                      help="Instance store image id to run initial instance from", default="emi-")
    
    parser.add_option("-u", "--user", type="string", dest="user",
                      help="User to run script against", default="admin")
    
    parser.add_option("-z", "--zone", type="string", dest="zone",
                      help="AZ to run script against", default="PARTI00")
    
    parser.add_option("-c", "--config", type="string", dest="config",
                      help="Config file to use", default=None)
    
    parser.add_option("-a", "--account", type="string", dest="account",
                      help="Account to run script against", default="eucalyptus")
    
    parser.add_option("-t", "--type", type="string", dest="itype",
                      help="Type of instance to launch when building image (ebs or Default:instance-store)", default="instance-store")
    
    parser.add_option("-g", "--group", type="string", dest="group",
                      help="Group to run script against", default="default")
    
    parser.add_option( "--prefix", dest="prefix", type="string",
                      help="Prefix to tack on to keypairs which get created", default="keypair")
    
    parser.add_option("--windows", dest="windows", action="store_true",
                      help="Register as windows image, default is linux",default=False)
    
    parser.add_option("-n", "--name", type="string", dest="name",
                      help="Name used when registering image (default=bfebs_<url's image>", default=None)
    
    parser.add_option("-d", "--dot", dest="dot", action="store_false",
                      help="Sets delete on terminate to false, default is true", default=True)
    
    parser.add_option("--md5", dest="md5sum", type="string", 
                      help="md5sum of remote file. Used for checking file transfer and write", default=None)
    
    parser.add_option("--eof", dest="eof", action="store_false",
                      help="Sets exit on failure to false", default=True)
    
    parser.add_option("--no-clean", dest="clean", action="store_false",
                      help="Sets clean to false, will not clean up instances/volumes at script exit", default=True)
    
    parser.add_option("-p", dest="password", type="string",
                      help="Password", default=None) 
    
    parser.add_option("--credpath", dest="credpath", type="string", 
                      help="path to local creds", default=None)

    (options, args) = parser.parse_args()
     
    config = options.config
    credpath = options.credpath
    if (config is None) and (credpath is None):
        pmsg ("Missing config file or cred path in args")
        parser.print_help()
        exit(1)
        
    url = options.url 
    if (url is None):
        pmsg ("Missing url in command")
        parser.print_help()
        exit(1)
    
    img = options.img
    user = options.user
    account = options.account
    zone = options.zone
    itype = options.itype
    group_name = options.group
    prefix = options.prefix
    windows = options.windows
    name = options.name
    dot = options.dot
    md5sum = options.md5sum
    eof = options.eof
    clean = options.clean
    password = options.password
    credpath = options.credpath
    instance = None
    volume = None
    keypair=None
    
    

        
    if (name is None):
        name = "bfebs_"+(url.split('/').pop())
        
    pmsg("url:"+str(url)+"\nimg:"+str(img)+"\nuser:"+str(user)+"\naccount:"+str(account)+"\nzone:"+str(zone)+"\ntype:"+str(itype)+"\ngroup:"+str(group_name)+
             "\nprefix:" + str(prefix)+"\nwindows:"+str(windows)+"\nname:"+str(name)+"\ndot:"+str(dot)+"\nmd5sum:"+str(md5sum)+"\nconfig:"+str(config))
    
    #Define the bytes per gig
    gig = 1073741824
    #Define timeout based on gig, for transfer disk writing,etc.
    time_per_gig = 300
    #Number of ping attempts used to test instance state, before giving up on a running instance 
    ping_retry=100
    #The eutester cloud tester object 
    tester = Eucaops( password=password, config_file=config, credpath=credpath)
    
    #sets tester to throw exception upon failure
    if (options.eof):
        tester.exit_on_fail = 1
    else:
        tester.exit_on_fail = 0 
   
    try:
        ### Create security group if it does not exist. Add ssh authorization to it. 
        try:
            group = tester.add_group(group_name)
            tester.authorize_group_by_name(group.name)
            tester.authorize_group_by_name(group.name,protocol="icmp",port=-1)
        except Exception, e:    
            raise Exception("Error when setting up group:"+str(group_name)+", Error:"+str(e))
            
        
        
        #Get the remote file size from the http header of the url given
        try:        
            url = url.replace('http://','')
            host = url.split('/')[0]
            path = url.replace(host,'')
            pmsg("get_remote_file, host("+host+") path("+path+")")
            conn=httplib.HTTPConnection(host)
            conn.request("HEAD", path)  
            res=conn.getresponse()
            fbytes=int(res.getheader('content-length'))
            pmsg("content-length:"+str(fbytes))
            rfsize= ( ((fbytes/gig)+1) or 1)
            pmsg("Remote file size: "+ str(rfsize) + "g")
            conn.close() 
        except Exception, e:
            pmsg("Failed to get remote file size...")
            raise e
        try:
            instance = None    
            keys = tester.get_all_current_local_keys()
            
            if keys != []:
                pmsg("Looks like we had some local keys looking through them now...")
                for keypair in keys:
                    pmsg('looking for instances using keypair:'+keypair.name)
                    instances = tester.get_instances(state='running',key=keypair.name)
                    if instances != []:
                        instance = instances[0]
                        pmsg('Found usable instance:'+instance.id+'using key:'+keypair.name)
                        break
        except Exception, e:
            pmsg("Failed to find a pre-existing isntance we can connect to:"+str(e))
            pass
        
                
        if instance is None:   
            #Create a new keypair to use for this test if we didn't find one
            if keypair is None:
                try:
                    keypair = tester.add_keypair(prefix + "-" + str(time.time()))
                except Exception, e:
                    raise Exception("Error when adding keypair. Error:"+str(e))
            
            pmsg("Attempting to launch initial instance now...")
            try:
                #Grab an emi based on our given criteria
                image=tester.get_emi(emi=img, root_device_type=itype)
                pmsg("Got emi to use:"+image.id)
            
                #Launch an instance from the emi we've retrieved, instance is returned in the running state
                tester.poll_count = 96 
                reservation=tester.run_instance(image, keypair=keypair.name, group=group_name,zone=zone, )
                if (reservation is not None):
                    instance = reservation.instances[0]
                    pmsg("Launched instance:"+instance.id)
                else:
                    raise Exception("Failed to run an instance using emi:"+image.id)
            except Exception, e:
                pmsg("Doh, error while trying to run instance using emi:"+image.id)
                raise e
            
        try:
            keypath = os.getcwd() + "/" + keypair.name + ".pem" 
            pmsg('Getting contents from /dev...')
            before_attach = instance.get_dev_dir()
                
        except Exception, ie:
            raise Exception("Failed to retrieve contents of /dev dir from instance, Error:"+str(ie))
    
        pmsg("Got snapshot of /dev, now creating a volume of "+str(rfsize)+" to attach to our instance...")
        volume=tester.create_volume(zone, rfsize)
        dev = "/dev/sdf"
        
        pmsg("Attaching Volume ("+volume.id+") to instance("+instance.id+") trying dev("+dev+")")
        try:
            volume.attach(instance.id, "/dev/sdf")
        except Exception, ve:
            raise Exception("Error attaching volume:"+str(volume.id)+", Error:"+str(ve))
            
        
        pmsg("Sleeping and waiting for volume to attach fully to instance")
        tester.sleep(20)
        for x in range(0,10):
            #after_attach = instance.sys('ls -1 /dev/| grep "sd\|vd"')
            after_attach = instance.get_dev_dir()
            #The attached device should be the difference in our /dev snapshots
            new_devices = tester.diff(after_attach, before_attach)
            if new_devices == []:
                pmsg(" Attempt "+str(x)+" Volume attached but not found on guest" + str(instance) )
                pmsg("after attach:"+"".join(after_attach))
            else:
                break
            time.sleep(5)
         
        if new_devices == []:
            raise Exception("Fail, Volume attached but not found on guest" + str(instance) )
        attached_block_dev =  "/dev/"+new_devices[0].strip()
        pmsg("Attached to guest dev:"+attached_block_dev+"\nSplat our remote image into volume")
        
        #Get the md5 of the remote image before writing it to the volume for comparison purposes
        timeout=rfsize*time_per_gig+200
        if ( md5sum is None ):
            pmsg("MD5sum not provided, getting it now...")
            cmd="curl -s "+url+" | md5sum "  
            md5sum=instance.sys(cmd ,  timeout=timeout)[0]
            md5sum=md5sum.split(' ')[0]
            pmsg("The md5sum of the remote image: "+str(md5sum))
            
        #Download the remote image, write it directly to our volume
        cmd="curl "+url+" > "+attached_block_dev+" && echo 'GOOD' && sync"
        try:
            pmsg("Issuing cmd:"+cmd+" , timeout:"+str(timeout))
            output=instance.sys(cmd,  timeout=timeout)
            pmsg("Curl output:"+"".join(output))
            result = output[len(output)-1]
            result = result.split(' ')[0]
            pmsg("curl cmd's parsed result:"+result)
        except Exception, e:
            raise Exception("failed to curl image into block dev: "+str(e))
        #Make sure the curl command did not return error
        if (re.match('GOOD',result)):
            pmsg("Our write to volume returned GOOD")
        else:
            raise Exception("Our write to volume failed:"+str(result))
      
        #Get the md5sum of the volume to compare to our previous md5         
        cmd="head -c "+str(fbytes)+" "+attached_block_dev+" | md5sum "
        md5sum2=instance.sys(cmd ,  timeout=timeout)[0]
        md5sum2 = md5sum2.split(' ')[0]
        if ( md5sum != md5sum2  ):
            pmsg ("md5sum failed ms5sum1:"+md5sum+" vs md5sum2:"+md5sum2)
            raise Exception ("md5 sums did not match")
        else:
            pmsg("Md5sum is good. Done splatting image, detaching volume...")
        time.sleep(5)
        tester.detach_volume(volume, timeout=timeout)
        
        pmsg("Creating snapshot from our splatted volume...")
        snapshot = tester.create_snapshot(volume.id, waitOnProgress=15, timeout=timeout)
        
        pmsg("Snapshot complete, register it as an emi with name:"+name+"...")
        bfebs_emi = tester.register_snapshot(snapshot, windows=windows, name=name, dot=dot)
        pmsg("Done. Image registered as:"+str(bfebs_emi))
    
    except Exception, e:
        print "\n\n\n\n\nscript failed\n\n\n\n\n"
        print "-------------ERROR---------------"
        print str(e)
        print "---------------------------------"
    except KeyboardInterrupt:
        pmsg("Caught keyboard interrupt...")
    finally:
        #If clean flag is set, terminate instances and delete volumes
        if (options.clean):
            pmsg("script complete, terminate instance, delete volume, and exit")
            if (instance is not None):
                instance.terminate()
                time.sleep(10)
            if (volume is not None):
                volume.delete()
        else:
            pmsg("script complete. --no-clean is set, leaving test state intact post execution")
        
        
