from eutester import Eutester
from eucaops_api import Eucaops_api
import time
import re
import sys

class Eucaops(Eutester,Eucaops_api):
    
    def __init__(self, config_file="cloud.conf", hostname=None, password=None, keypath=None, credpath=None, aws_access_key_id=None, aws_secret_access_key = None, debug=0):
        super(Eucaops, self).__init__(config_file, hostname, password, keypath, credpath, aws_access_key_id, aws_secret_access_key, debug)
        self.poll_count = 24   
           
    def create_bucket(self,bucket_name):
        """
        Create a bucket.  If the bucket already exists and you have
        access to it, no error will be returned by AWS.
        Note that bucket names are global to S3
        so you need to choose a unique name.
        """
        # First let's see if we already have a bucket of this name.
        # The lookup method will return a Bucket object if the
        # bucket exists and we have access to it or None.
        bucket = self.walrus.lookup(bucket_name)
        if bucket:
            print 'Bucket (%s) already exists' % bucket_name
        else:
                # Let's try to create the bucket.  This will fail if
                # the bucket has already been created by someone else.
            try:
                bucket = self.walrus.create_bucket(bucket_name)
            except self.walrus.provider.storage_create_error, e:
                print 'Bucket (%s) is owned by another user' % bucket_name
        return bucket
    
    def upload_object_file(self, bucket_name, key_name, path_to_file):
        """
        Write the contents of a local file to walrus and also store custom
        metadata with the object.
        bucket_name   The name of the walrus Bucket.
        key_name      The name of the object containing the data in walrus.
        path_to_file  Fully qualified path to local file.
        """
        bucket = s3.lookup(bucket_name)
        # Get a new, blank Key object from the bucket.  This Key object only
        # exists locally until we actually store data in it.
        key = bucket.new_key(key_name)
        key.set_contents_from_filename(path_to_file)
        return key
    
    def add_keypair(self,key_name=None):
        if key_name==None:
            key_name = "keypair-" + str(int(time.time())) 
        print "Looking up keypair " + key_name 
        key = self.ec2.get_all_key_pairs(keynames=[key_name])    
        if key == []:
            print 'Creating keypair: %s' % key_name
            # Create an SSH key to use when logging into instances.
            key = self.ec2.create_key_pair(key_name)
            # AWS will store the public key but the private key is
            # generated and returned and needs to be stored locally.
            # The save method will also chmod the file to protect
            # your private key.
            key.save(self.key_dir)
            return key
        else:
            print "Key " + key_name + " already exists"
    
    def delete_keypair(self,keypair):
        name = keypair.name
        print "Sending delete for keypair: " + name
        keypair.delete()
        keypair = self.ec2.get_all_key_pairs(keynames=[name])
        if len(keypair) > 0:
            self.fail("Keypair found after attempt to delete it")
        return
    
    def add_group(self, group_name=None ):
        group_name = "group-" + str(int(time.time()))     
        if self.check_group(group_name):
            print "Group " + group_name + " already exists"
            return group[0]
        else:
            print 'Creating Security Group: %s' % group_name
            # Create a security group to control access to instance via SSH.
            group = self.ec2.create_security_group(group_name, group_name)
            return group
    
    def delete_group(self, group):
        name = group.name
        print "Sending delete for group: " + name
        group.delete()
        if self.check_group(name):
            self.fail("Group found after attempt to delete it")
        return
    
    def check_group(self, group_name):
        print "Looking up group " + group_name
        group = self.ec2.get_all_security_groups(groupnames=[group_name])
        if group == []:
             return False
        else:
             return True
    
    def authorize_group(self,group_name="default", port=22, protocol="tcp", cidr_ip="0.0.0.0/0"):
        try:
            print "Attempting authorization of group"
            self.ec2.authorize_security_group_deprecated(group_name,ip_protocol=protocol, from_port=port, to_port=port, cidr_ip=cidr_ip)
        except self.ec2.ResponseError, e:
            if e.code == 'InvalidPermission.Duplicate':
                print 'Security Group: %s already authorized' % group_name
            else:
                raise
    
    def wait_for_instance(self,instance, state="running"):
        poll_count = self.poll_count
        print "Beginning poll loop for instance " + str(instance) + " to go to " + state
        while (instance.state != state) and (poll_count > 0):
            poll_count -= 1
            time.sleep(10)
            instance.update()
        print "Done. Waited a total of " + str( self.poll_count - poll_count) + " seconds"
        if poll_count == 0:
                self.fail(str(instance) + " did not enter the proper state and was left in " + instance.state)
        print str(instance) + ' is now in ' + instance.state

    def wait_for_reservation(self,reservation, state="running"):
        print "Beginning poll loop for the " + str(len(reservation.instances))   + " found in " + str(reservation)
        for instance in reservation.instances:
            self.wait_for_instance(instance, state)
    
    def create_volume(self, azone, size=1, snapshot=None):
        """
        Create a new EBS volume
        """
        # Determine the Availability Zone of the instance
        poll_count = self.poll_count
        volume = self.ec2.create_volume(size, azone)
        # Wait for the volume to be created.
        print "Polling for volume to become available"
        while volume.status != 'available' and (poll_count > 0):
            poll_count -= 1
            time.sleep(5)
            volume.update()
        print "Done. Waited a total of " + str(self.poll_count - poll_count) + " seconds\nVolume in " + volume.status + " state"
    
    def get_emi(self, emi="emi-"):
        images = self.ec2.get_all_images()
        for image in images:
            if re.match(emi, image.id):
                return image
        raise Exception("Unable to find an EMI")
    
    def run_instance(self, image=None, keypair=None, group=None, type=None, zone=None, min=1, max=1):
        if image == None:
            images = self.ec2.get_all_images()
            for emi in images:
                if re.match("emi",emi.name):
                    image = emi
        print "Attempting to run image " + str(image)
        reservation = image.run(key_name=keypair,security_groups=group,instance_type=type, placement=zone, min_count=min, max_count=max)
        self.wait_for_reservation(reservation)
        for instance in reservation.instances:
            if instance.state != "running":
                self.fail("Instance " + instance.id + " now in " + instance.state  + " state")
            else:
                print "Instance " + instance.id + " now in " + instance.state  + " state"
        return reservation
    
    def get_available_vms(self, type=None):
        ### Need to update this to work for a particular availability zone
        az_verbose_out = self.sys("euca-describe-availability-zones verbose")
        vmtypes = {"m1.small": 0,"c1.medium":0, "m1.large":0, "m1.xlarge":0,"c1.xlarge":0}
        for type1,avail in vmtypes.iteritems():
            ### Parse out each type of VM then get the free ones
            vmtypes[type1] = int(self.grep( str(type1) , az_verbose_out)[0].split()[3])
            #print type1 + ":" + str(vmtypes[type1])
        if type==None:
            return vmtypes
        else:
            return int(vmtypes[type])
    
    def release_address(self, ip=None):       
        if ip==None:
            ## Clear out all addresses found
            print "Releasing all used addresses"
            address_output = self.sys("euca-describe-addresses")
            addresses = self.grep("ADDRESS",address_output)
            total_addresses = len(addresses)
            for address in addresses:
                if re.search("nobody", address) == None:
                    self.sys("euca-release-address " + address.split()[1] )
            address_output = self.sys("euca-describe-addresses")
            free_addresses = self.grep("nobody", address_output)
            if len(free_addresses) < total_addresses:
                self.fail("Some addresses still in use after attempting to release")
        else:
            print "Releasing address " + ip
            self.sys("euca-release-address " + ip )
            address_output = self.sys("euca-describe-addresses")
            free_addresses = self.grep( ip + ".*nobody", address_output)
            if len(free_addresses) < 1:
                self.fail("Address still in use after attempting to release")
            
    def terminate_instances(self, reservation=None):
        ### If a reservation is not passed then kill all instances
        if reservation==None:
#            reservations.stop_all()
            reservations = self.ec2.get_all_instances()
            for res in reservations:
                for instance in res.instances:
                    print "Sending terminate for " + str(instance)
                    instance.terminate()
                self.wait_for_reservation(res, state="terminated")
        ### Otherwise just kill this reservation
        else:
            for instance in reservation.instances:
                    print "Sending terminate for " + str(instance)
                    instance.terminate()
            self.wait_for_reservation(reservation, state="terminated")
            
    def modify_property(self, property, value):
        command = self.eucapath + "/usr/sbin/euca-modify-property -p " + property + "=" + value
        if self.found(command, property):
            self.test_name("Properly modified property")
        else:
            self.fail("Could not modify " + property)
    
    def get_master(self, component="clc"):
        service = "eucalyptus"
        if component == "sc":
            service = "storage"
        if component == "ws":
            service = "walrus"
        if component == "cc":
            service = "cluster"
        print "Looking for enabled " + component + " in current connection"
        ### TRY with the open connection if it fails, then try to
        machines = self.get_component_machines("clc")
        old_ssh = self.ssh
        first = ""
        second = ""
        
        ### GO through both clcs and check which ip it thinks is enabled for this service type
        for clc in machines:
            print ":" + clc + ":" 
            self.ssh = self.create_ssh(clc, "foobar")
            service_url = self.sys( self.eucapath + "/usr/sbin/euca-describe-services | egrep -e 'SERVICE[[:space:]]"+ service + "' | grep ENABLED | awk '{print $7}'")
            ### Parse out the IP from this url
            if first == "":
                first = service_url[0].split(":")[1].strip("/") 
            else:
                second =  service_url[0].split(":")[1].strip("/")
        self.ssh = old_ssh
        if first == second:
            print "Found matching enabled " + component + " as " + first
            return first
        else:
            self.fail("Found a mismatch in the first and second CLCs checked as to which was master")
            self.fail("First thought: " + first + " Second Thought: " + second)
            
       
        
        
        
        

