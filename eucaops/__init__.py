# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: vic.iglesias@eucalyptus.com
# Author: matt.clark@eucalyptus.com

from iamops import IAMops
from ec2ops import EC2ops
from s3ops import S3ops


class Eucaops(EC2ops,S3ops,IAMops):
    
    def __init__(self, config_file=None, password=None, keypath=None, credpath=None, aws_access_key_id=None, aws_secret_access_key = None,  account="eucalyptus", user="admin", username=None, region=None, boto_debug=0):
        super(Eucaops, self).__init__(config_file=config_file,password=password, keypath=keypath, credpath=credpath, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key,account=account, user=user, username=username, region=region, boto_debug=boto_debug)
        self.test_resources = {}
        self.setup_s3_resource_trackers()
        self.setup_ec2_resource_trackers()
    
    def get_available_vms(self, type=None, zone=None):
        """
        Get available VMs of a certain type or return a dictionary with all types and their available vms
        type        VM type to get available vms 
        """
        
        zones = self.ec2.get_all_zones('verbose') 
        if type == None:
            type = "m1.small"
        ### Look for the right place to start parsing the zones
        zone_index = 0
        if zone != None: 
            while zone_index < len(zones):
                current_zone = zones[zone_index]
                if re.search( zone, current_zone.name):
                    break
                zone_index += 7
            if zone_index > (len(zones) - 1)   :
                self.fail("Was not able to find AZ: " + zone)
                raise Exception("Unable to find Availability Zone")    
        else:
            zone = zones[0].name
            
        ### Inline switch statement
        type_index = {
                      'm1.small': 2,
                      'c1.medium': 3,
                      'm1.large': 4,
                      'm1.xlarge': 5,
                      'c1.xlarge': 6,
                      }[type] 
        type_state = zones[ zone_index + type_index ].state.split()
        self.debug("Finding available VMs: Partition=" + zone +" Type= " + type + " Number=" +  str(int(type_state[0])) )
        return int(type_state[0])
        
    
    
            
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
    
   
    def cleanup_artifacts(self):
        self.debug("Starting cleanup of artifacts")
        for key,array in self.test_resources.iteritems():
            for item in array:
                try:
                    ### SWITCH statement for particulars of removing a certain type of resources
                    self.debug("Deleting " + str(item))
                    if isinstance(item, Image):
                        item.deregister()
                    elif isinstance(item, Reservation):
                        self.terminate_instances(item)
                    elif isinstance(item, Volume):
                        try:
                            self.detach_volume(item)
                        except:
                            pass
                        self.delete_volume(item)
                    else:
                        item.delete()
                except Exception, e:
                    self.fail("Unable to delete item: " + str(item) + "\n" + str(e))
                    
    def get_current_resources(self,verbose=False):
        '''Return a dictionary with all known resources the system has. Optional pass the verbose=True flag to print this info to the logs
           Included resources are: addresses, images, instances, key_pairs, security_groups, snapshots, volumes, zones
        
        '''
        current_artifacts = dict()
        current_artifacts["addresses"] = self.ec2.get_all_addresses()
        current_artifacts["images"] = self.ec2.get_all_images()
        current_artifacts["instances"] = self.ec2.get_all_instances()
        current_artifacts["key_pairs"] = self.ec2.get_all_key_pairs()
        current_artifacts["security_groups"] = self.ec2.get_all_security_groups()
        current_artifacts["snapshots"] = self.ec2.get_all_snapshots()
        current_artifacts["volumes"] = self.ec2.get_all_volumes()
        current_artifacts["zones"] = self.ec2.get_all_zones()
        
        if verbose:
            self.info("Current resources in the system:\n" + pprint.pformat(current_artifacts))
        return current_artifacts
    

        
            
       
        
        
        
        

