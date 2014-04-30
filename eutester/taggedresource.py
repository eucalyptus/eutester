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

import time

class TaggedResource():
    def __init__(self):
        pass

    def create_tags(self, tags, timeout=600):
        self.tester.debug("Current tags: " + str(self.tags))
        self.tester.create_tags([self.id], tags)
        self.wait_for_tags(tags, timeout=timeout)

    def wait_for_tags(self, tags, creation=True, timeout=60):
        start= time.time()
        elapsed = 0
        while elapsed < timeout:
            self.update()
            applied_tags =  self.convert_tag_list_to_dict(self.tester.ec2.get_all_tags(filters={u'resource_id':self.id}))
            self.tester.debug("Current tags: " + str(applied_tags))
            found_keys = 0
            for key, value in tags.iteritems():
                if key in applied_tags:
                    found_keys += 1
                    self.tester.debug("Found key # " + str(found_keys)  + " out of " + str(len(tags))  + ":" + key)
            if creation:
                if found_keys == len(tags):
                    return True
                else:
                    pass
            else:
                if found_keys == 0:
                    return True
                else:
                    pass
            elapsed = int(time.time() - start)
            time.sleep(5)
        raise Exception("Did not apply tags within " + str(timeout) + " seconds")

    def convert_tag_list_to_dict(self, list):
        new_dict = {}
        for tag in list:
            new_dict[tag.name] = tag.value
        return new_dict

    def delete_tags(self, tags, timeout=600):
        self.tester.debug("Current tags: " + str(self.tags))
        self.tester.delete_tags([self.id], tags)
        self.wait_for_tags(tags, creation=False, timeout=timeout)