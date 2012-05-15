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
from eutester import Eutester
import re

class IAMEntity(object):
    def __init__(self, name, path, arn, id):
        self.name = name
        self.path = path
        self.arn = arn
        self.id = id

class IAMops(Eutester):
    
    def return_entity(self, full_response, type):
        top_level_container = "create_" + type + "_response"
        result_level_container = "create_" + type + "_result"
        result = full_response[top_level_container][result_level_container][type]
        return IAMEntity( result[type + "_name"], result["path"], result["arn"], result[type + "_id"])
    
    def create_user(self, user_name,path="/"):
        self.debug("Attempting to create user: " + user_name)
        return self.return_entity(self.euare.create_user(user_name, path), "user")
    
    def create_group(self, group_name,path="/"):
        self.debug("Attempting to create group: " + group_name)
        return self.return_entity(self.euare.create_group(group_name, path), "group")
    
    def delete_group(self, group_name):
        self.debug("Deleting group " + group_name)
        self.euare.delete_group(group_name)
        
    def delete_user(self, user_name):
        self.debug("Deleting user " + user_name)
        self.euare.delete_user(user_name)
        
    def attach_policy_user(self, user_name, policy_name, policy_json):
        self.debug("Attaching the following policy to " + user_name + ":" + policy_json)
        self.euare.put_user_policy(user_name, policy_name, policy_json)
    
    def attach_policy_group(self, group_name, policy_name, policy_json):
        self.debug("Attaching the following policy to " + group_name + ":" + policy_json)
        self.euare.put_group_policy(group_name, policy_name, policy_json)
        
        
    
        
    