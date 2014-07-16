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
# Author: Vic Iglesias vic.iglesias@eucalyptus.com
#
from locust import task, TaskSet

class EC2Read(TaskSet):
    @task(10)
    def get_instances(self):
        self.client.time_operation(self.client.get_instances)

    @task(10)
    def get_volumes(self):
        self.client.time_operation(self.client.get_volumes)


class EC2Create(TaskSet):

    @task(1)
    def run_instances(self):
        reservation = self.client.time_operation(self.client.run_instance)
        self.client.time_operation(self.client.terminate_instances, reservation)

    @task(1)
    def create_volumes(self):
        volumes = self.client.time_operation(self.client.create_volumes,
                                             zone="one")
        self.client.time_operation(self.client.delete_volumes, volumes)


class S3Operations(TaskSet):
    @task(10)
    def list_buckets(self):
        self.client.time_operation(self.client.s3.get_all_buckets)

    @task(1)
    def create_bucket(self):
        bucket = self.client.time_operation(self.client.s3.create_bucket,
                                            str(int(time.time())).
                                            lower())
        if bucket:
            self.client.time_operation(self.client.s3.delete_bucket, bucket)

