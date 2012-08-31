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
'''
Created on Apr 25, 2012
@author: vic.iglesias@eucalyptus.com
'''

import pickle
import ConfigParser
import random 
import os
import string
class EuPopulator(object):
    '''
    This class is intended to read in a config file using ConfigParser, then create resources based on the config file
    It is also able to serialize the current resources in a cloud into a file, read in that file and verify that the resources still
    exist in the same way. Serialization is done with Pickle. 
    '''

    def __init__(self, eucaops, config_file = None):
        '''
        Constructor for EuPopulator:
            eutester         A eutester object that we can use for connections
            config_file      Filename of the config describing what resources to populate
        '''
        self.tester = eucaops
        if config_file is None:
            self.defaults = ConfigParser.SafeConfigParser()
            ### Global 
            self.defaults.add_section('global')
            partition = self.tester.ec2.get_all_zones()[0].name
            self.defaults.set('global', 'partition', partition)
            ### Volume 
            self.defaults.add_section('volumes')
            self.defaults.set('volumes', 'count', '2')
            self.defaults.set('volumes', 'min_size', '1')
            self.defaults.set('volumes', 'max_size', '3')
            
            ### Addresses
            self.defaults.add_section('addresses')
            self.defaults.set('addresses', 'count', '2')
            
            ### Snapshot 
            self.defaults.add_section('snapshots')
            self.defaults.set('snapshots', 'count', '2')
            self.defaults.set('snapshots', 'min_size', '1')
            self.defaults.set('snapshots', 'max_size', '3')
            self.defaults.set('snapshots', 'delete_volumes', 'false')
            
            ### Keypair 
            self.defaults.add_section('keypairs')
            self.defaults.set('keypairs', 'count', '2')
            self.defaults.set('keypairs', 'prefix', self.prefix_generator())
            
            ### Groups 
            self.defaults.add_section('security_groups')
            self.defaults.set('security_groups', 'count', '2')
            self.defaults.set('security_groups', 'prefix', self.prefix_generator())
            self.defaults.set('security_groups', 'port_min', '22')
            self.defaults.set('security_groups', 'port_max', '80')
            self.defaults.set('security_groups', 'protocol', 'tcp')
            self.defaults.set('security_groups', 'cidr', '0.0.0.0/0')
            
            ### Buckets
            self.defaults.add_section('buckets')
            self.defaults.set('buckets', 'count', '2')
            self.defaults.set('buckets', 'prefix', self.prefix_generator())
            self.defaults.set('buckets', 'add_keys', 'true')
            self.defaults.set('buckets', 'key_count', '2')
            self.defaults.set('buckets', 'key_prefix', self.prefix_generator())
            self.config = self.defaults

        else:
            config = ConfigParser.SafeConfigParser()
            config.read(config_file)
            self.config = config
        
        if self.config:
            with open('populate.cfg', 'wb') as configfile:
                self.config.write(configfile)
        else:
            raise Exception("Do not have a valid config file to use")
        
    def populate(self):
        '''
        Takes the config and creates each of the resources based on their parameters
        '''
        for section in self.config.sections():
            if section is not "global":
                try:
                    creation_method = getattr(EuPopulator, section)
                    creation_method(self)
                    print "Successfully created: " + section
                except Exception, e:
                    print "Unable to bind to resource creation method for: " + section + "\n Because of " + str(e)
                
    def volumes(self):
        print "Creating volumes"
        partition = self.config.get("global","partition")
        vol_count = self.config.getint("volumes", "count")
        min_size = self.config.getint("volumes", "min_size")
        max_size = self.config.getint("volumes", "max_size")
        
        for i in xrange(vol_count):
            size = random.randint(min_size, max_size)
            self.tester.create_volume(partition, size)
        
    def addresses(self):
        print "Allocating addreses"
        addr_count =  self.config.getint("addresses", "count")
        for i in xrange(vol_count):
            self.tester.allocate_address()
        
    def snapshots(self):
        print "Creating snapshots"
        partition = self.config.get("global","partition")
        snap_count = self.config.getint("snapshots", "count")
        min_size = self.config.getint("snapshots", "min_size")
        max_size = self.config.getint("snapshots", "max_size")
        delete_volumes = self.config.getboolean('snapshots', 'delete_volumes')
        
        for i in xrange(snap_count):
            size = random.randint(min_size, max_size)
            volume = self.tester.create_volume(partition, size)
            self.tester.create_snapshot(volume.id)
            if delete_volumes:
                self.tester.delete_volume(volume)
    
    def keypairs(self):
        print "Creating keypairs"
        key_count = self.config.getint("keypairs", "count")
        prefix = self.config.get("keypairs", "prefix")
        
        for i in xrange(key_count):
            self.tester.add_keypair(prefix + str(i))
        
    def security_groups(self):
        print "Creating security_groups"
        sg_count = self.config.getint("security_groups", "count")
        prefix = self.config.get("security_groups", "prefix")
        port_min = self.config.getint("security_groups", "port_min")
        port_max = self.config.getint("security_groups", "port_max")
        cidr = self.config.get("security_groups", "cidr")
        protocol = self.config.get("security_groups", "protocol")
        for i in xrange(sg_count):
            group = self.tester.add_group(prefix + str(i))
            self.tester.authorize_group(group, port=random.randint(port_min, port_max), protocol=protocol, cidr_ip=cidr)
    
    def buckets(self):
        print "Creating buckets"
        bucket_count = self.config.getint('buckets', 'count')
        bucket_prefix = self.config.get('buckets', 'prefix')
        add_keys = self.config.getboolean('buckets', 'add_keys')
        key_count = self.config.getint('buckets', 'key_count')
        key_prefix = self.config.get('buckets', 'key_prefix')
        
        for i in xrange(bucket_count):
            bucket = self.tester.create_bucket(bucket_prefix + str(i))
            if add_keys:
                for i in xrange(key_count):
                    self.tester.upload_object(bucket.name, key_prefix + str(i))
        
    def depopulate(self):
        self.tester.cleanup_artifacts()  
    
    def prefix_generator(self, size=6, chars=string.ascii_lowercase + string.digits):
        return ''.join(random.choice(chars) for x in range(size))
    
    def serialize_resources(self, output_file="cloud_objects.dat"):
        '''
        Takes a snapshot of the current resources in the system and puts them into a data structure, then pickles this struct into a file.
            output_file    Filename to use when outputing the serialized data, if this is None then the byte stream will be returned
        '''
        self.tester.debug("Serializing current resources")
        serialized = open(output_file, 'wb')
        all_resources = self.tester.get_current_resources()
        for type in all_resources:
            for object in all_resources[type]:
                print >>serialized, self.tester.get_all_attributes(object)
            
         
        serialized.close()
        self.tester.debug("Serialized resources can be found at: " + output_file)
        