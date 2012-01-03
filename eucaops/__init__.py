from eutester import Eutester
from eucaops_api import Eucaops_api
import time
import re
import sys

class Eucaops(Eutester,Eucaops_api):
    
    def __init__(self, config_file="cloud.conf", hostname=None, password=None, keypath=None, credpath=None, aws_access_key_id=None, aws_secret_access_key = None,account="eucalyptus",user="admin", debug=0):
        super(Eucaops, self).__init__(config_file, hostname, password, keypath, credpath, aws_access_key_id, aws_secret_access_key,account, user, debug)
        self.poll_count = 24
        self.test_resources = {}
        self.test_resources["snapshots"] = []
        self.test_resources["instances"] = []
        self.test_resources["keypairs"] = []
        self.test_resources["groups"] = []
        self.test_resources["addresses"] = []
        self.test_resources["buckets"] = []
        self.test_resources["keys"] = []
           
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
                return None
            self.my_buckets.append(bucket)
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
        """
        Add a keypair with name key_name unless it already exists
        key_name      The name of the keypair to add and download.
        """
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
        """
        Delete the keypair object passed in and check that it no longer shows up
        keypair      Keypair object to delete and check
        """
        name = keypair.name
        print "Sending delete for keypair: " + name
        keypair.delete()
        keypair = self.ec2.get_all_key_pairs(keynames=[name])
        if len(keypair) > 0:
            self.fail("Keypair found after attempt to delete it")
        return
    
    def add_group(self, group_name=None ):
        """
        Add a security group to the system with name group_name, if it exists dont create it
        group_name      Name of the security group to create
        """
        if group_name == None:
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
        """
        Delete the group object passed in and check that it no longer shows up
        group      Group object to delete and check
        """
        name = group.name
        print "Sending delete for group: " + name
        group.delete()
        if self.check_group(name):
            self.fail("Group found after attempt to delete it")
        return
    
    def check_group(self, group_name):
        """
        Check if a group with group_name exists in the system
        group_name      Group name to check for existence
        """
        print "Looking up group " + group_name
        group = self.ec2.get_all_security_groups(groupnames=[group_name])
        if group == []:
             return False
        else:
             return True
    
    def authorize_group(self,group_name="default", port=22, protocol="tcp", cidr_ip="0.0.0.0/0"):
        """
        Authorize the group with group_name, 
        group_name      Name of the group to authorize, default="default"
        port            Port to open, default=22
        protocol        Protocol to authorize, default=tcp
        cidr_ip         CIDR subnet to authorize, default="0.0.0.0/0" everything
        """
        try:
            print "Attempting authorization of group"
            self.ec2.authorize_security_group_deprecated(group_name,ip_protocol=protocol, from_port=port, to_port=port, cidr_ip=cidr_ip)
        except self.ec2.ResponseError, e:
            if e.code == 'InvalidPermission.Duplicate':
                print 'Security Group: %s already authorized' % group_name
            else:
                raise
    
    def wait_for_instance(self,instance, state="running"):
        """
        Wait for the instance to enter the state
        instance      Boto instance object to check the state on
        state        state that we are looking for
        """
        poll_count = self.poll_count
        print "Beginning poll loop for instance " + str(instance) + " to go to " + state
        while (instance.state != state) and (poll_count > 0):
            poll_count -= 1
            time.sleep(10)
            instance.update()
        print "Done. Waited a total of " + str( (self.poll_count - poll_count) * 10 ) + " seconds"
        if poll_count == 0:
                self.fail(str(instance) + " did not enter the proper state and was left in " + instance.state)
        print str(instance) + ' is now in ' + instance.state

    def wait_for_reservation(self,reservation, state="running"):
        """
        Wait for the an entire reservation to enter the state
        reservation  Boto reservation object to check the state on
        state        state that we are looking for
        """
        print "Beginning poll loop for the " + str(len(reservation.instances))   + " found in " + str(reservation)
        for instance in reservation.instances:
            self.wait_for_instance(instance, state)
    
    def create_volume(self, azone, size=1, snapshot=None):
        """
        Create a new EBS volume then wait for it to go to available state, size or snapshot is mandatory
        azone        Availability zone to create the volume in
        size         Size of the volume to be created
        snapshot     Snapshot to create the volume from
        """
        # Determine the Availability Zone of the instance
        poll_count = self.poll_count
        poll_interval = 10
        print "Sending create volume request"
        volume = self.ec2.create_volume(size, azone)
        # Wait for the volume to be created.
        print "Polling for volume to become available"
        while volume.status != 'available' and (poll_count > 0):
            poll_count -= 1
            time.sleep(poll_interval)
            volume.update()
        if poll_count == 0:
            self.fail(str(volume) + " never went to available and stayed in " + volume.status)
            print "Deleting volume that never became available"
            volume.delete()
            return None
        print "Done. Waited a total of " + str( (self.poll_count - poll_count) * poll_interval) + " seconds\nVolume in " + volume.status + " state"
        return volume
    
    def delete_volume(self, volume):
        """
        Delete the EBS volume then check that it no longer exists
        volume        Volume object to delete
        """
        self.ec2.delete_volume(volume.id)
        print "Sent delete for volume: " +  volume.id  
        poll_count = 5
        volume.update()
        while ( volume.status != "deleted") and (poll_count > 0):
            poll_count -= 1
            volume.update()
            print str(volume) + " in " + volume.status
            self.sleep(10)

        if poll_count == 0:
            self.fail(str(volume) + " left in " +  volume.status)
            return volume
    
    def delete_all_volumes(self):
        volumes = self.ec2.get_all_volumes()
        for volume in volumes:
            self.delete_volume(volume.id)
    
    def detach_volume(self, volume):
        volume.detach()
        print "Sent detach for volume: " + volume.id
        poll_count = 5
        while ( volume.status != "available") and (poll_count > 0):
            poll_count -= 1
            print str(volume) + " in " + volume.status
            self.sleep(5)
        volume.update() 
        if poll_count == 0:
            self.fail(str(volume) + " left in " +  volume.status)
            return volume
        
    def get_emi(self, emi="emi-"):
        """
        Get an emi with name emi, or just grab any emi in the system
        emi        ID of the emi to return
        """
        images = self.ec2.get_all_images()
        for image in images:
            if re.match(emi, image.id):
                return image
        raise Exception("Unable to find an EMI")
        return
    
    def run_instance(self, image=None, keypair=None, group="default", type=None, zone=None, min=1, max=1):
        """
        Run instance/s and wait for them to go to the running state
        image      Image object to use, default is pick the first emi found in the system
        keypair    Keypair name to use for the instances, defaults to none
        group      Security group name to apply to this set of instnaces, defaults to none
        type       VM type to use for these instances, defaults to m1.small
        zone       Availability zone to run these instances
        min        Minimum instnaces to launch, default 1
        max        Maxiumum instances to launch, default 1
        """
        if image == None:
            images = self.ec2.get_all_images()
            for emi in images:
                if re.match("emi",emi.name):
                    image = emi         
        print "Attempting to run image " + str(image) + "in group " + group
        reservation = image.run(key_name=keypair,security_groups=[group],instance_type=type, placement=zone, min_count=min, max_count=max)
        self.wait_for_reservation(reservation)
        for instance in reservation.instances:
            if instance.state != "running":
                self.fail("Instance " + instance.id + " now in " + instance.state  + " state")
            else:
                print "Instance " + instance.id + " now in " + instance.state  + " state"
        return reservation
    
    def get_available_vms(self, type=None):
        """
        Get available VMs of a certain type or return a dictionary with all types and their available vms
        type        VM type to get available vms 
        """
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
        """
        Release all addresses or a particular IP
        ip        IP to release
        """   
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
                print "Some addresses still in use after attempting to release"
                #self.fail("Some addresses still in use after attempting to release")
        else:
            print "Releasing address " + ip
            self.sys("euca-release-address " + ip )
            address_output = self.sys("euca-describe-addresses")
            free_addresses = self.grep( ip + ".*nobody", address_output)
            if len(free_addresses) < 1:
                print "Some addresses still in use after attempting to release"
                #self.fail("Address still in use after attempting to release")
            
    def terminate_instances(self, reservation=None):
        """
        Terminate instances in the system
        reservation        Reservation object to terminate all instances in, default is to terminate all instances
        """
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
        """
        Modify a eucalyptus property through the command line euca-modify-property tool
        property        Property to modify
        value           Value to set it too
        """
        command = self.eucapath + "/usr/sbin/euca-modify-property -p " + property + "=" + value
        if self.found(command, property):
            self.test_name("Properly modified property")
        else:
            self.fail("Could not modify " + property)
    
    def get_master(self, component="clc"):
        """
        Find the master of any type of component and return its IP, by default returns the master CLC
        component        Component to find the master, possible values ["clc", "sc", "cc", "ws"]
        """
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
            
       
        
        
        
        

