#!/usr/bin/env python

from __future__ import division
import time
import os
import hashlib
import tempfile
from math import ceil
from cStringIO import StringIO
from concurrent.futures import ThreadPoolExecutor
from eucaops import Eucaops
from eucaops import S3ops
from eutester.eutestcase import EutesterTestCase


class OSGConcurrency(EutesterTestCase):

    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("-b", "--buckets", type=int, default=5)
        self.parser.add_argument("-o", "--objects", type=int, default=5)
        self.parser.add_argument("-T", "--threads", type=int, default=5)
        self.parser.add_argument("-S", "--object-size", type=int, default=64, help="Object size in KB")
        self.parser.add_argument("-M", "--mpu-threshold", type=int, default=5120,
                                 help="Multipart upload is used when the object size is bigger than the mpu-threshold "
                                      "value in Kilobyte. Any value less than 5120KB will result single file upload. "
                                      "Default value is used when not passed as an argument.")
        self.get_args()
        # Setup basic eutester object
        if self.args.region:
            self.tester = S3ops( credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops(credpath=self.args.credpath, config_file=self.args.config,password=self.args.password)
        self.start = time.time()

        self.bucket_names = []
        self.bucket_name = "concurrency-" + str(int(self.start)) + "-"

        for i in xrange(self.args.buckets):
            bucket_name = self.bucket_name + str(i)
            self.bucket_names.append(bucket_name)
            self.tester.create_bucket(bucket_name)

        self.temp_files = []

    def clean_method(self):
        with ThreadPoolExecutor(max_workers=self.args.threads) as executor:
            for i in xrange(self.args.buckets):
                executor.submit(self.tester.clear_bucket(self.bucket_names[i]))
        for tf in self.temp_files:
            tf.close()

    def get_object(self, bucket, key_name, meta=True):
        """
        Writes the object to a temp file and returns the meta info of the object e.g hash, name.
        Returns the downloaded object when meta is set to False.
        """
        self.debug("Getting object '" + key_name + "'")
        ret_key = bucket.get_key(key_name)
        temp_object = tempfile.NamedTemporaryFile(mode="w+b", prefix="eutester-mpu")
        self.temp_files.append(temp_object)
        ret_key.get_contents_to_file(temp_object)
        if meta:
            return {'name': temp_object.name, 'hash': self.get_hash(temp_object.name)}
        return temp_object

    def single_upload(self, bucket, key_name, file_path):
        key = bucket.new_key(key_name)
        key.set_contents_from_filename(file_path)
        self.debug("Uploaded key '" + key_name + "' to bucket '" + bucket.name + "'")
        return key

    def multipart_upload(self, bucket, key_name, eufile):
        part_size = 1024 * self.args.mpu_threshold
        eufile.seek(0, os.SEEK_END)
        eufile_size = eufile.tell()
        num_parts = int(ceil(eufile_size / part_size))

        mpu = bucket.initiate_multipart_upload(key_name)
        self.debug("Initiated MPU. Using MPU Id: " + mpu.id)

        for i in range(num_parts):
            start = part_size * i
            file_part = open(eufile.name, 'rb')
            file_part.seek(start)
            data = file_part.read(part_size)
            file_part.close()
            mpu.upload_part_from_file(StringIO(data), i+1)
            self.debug("Uploaded part " + str(i+1) + " of '" + key_name + "' to bucket '" + bucket.name + "'")
        self.debug("Completing multipart upload of '" + key_name + "' to bucket '" +
                   bucket.name + "'" + " using mpu id: " + mpu.id)
        mpu.complete_upload()
        self.debug("Completed multipart upload of '" + key_name + "' to bucket '" + bucket.name + "'")

    def put_get_check(self, bucket_name, key_name, eu_file):
        """
        PUT objects, GET objects and then verify objects with object hash
        5MB is a hard-coded limit for MPU in OSG
        """
        bucket = self.tester.get_bucket_by_name(bucket_name)
        if (os.path.getsize(eu_file.name) > (5 * 1024 * 1024)) and (self.args.mpu_threshold >= (5 * 1024)):
            self.multipart_upload(bucket, key_name, eu_file)
        else:
            self.single_upload(bucket, key_name, eu_file.name)

        ret_object_meta = self.get_object(bucket, key_name)
        local_object_hash = self.get_hash(eu_file.name)

        self.debug("Matching local and remote hashes of object: " + eu_file.name)
        self.debug("Remote object: " + ret_object_meta['hash'])
        self.debug("Local object:  " + local_object_hash)
        if ret_object_meta['hash'] != local_object_hash:
            self.debug("return_object hash: " + ret_object_meta['hash'])
            self.debug("local_object hash: " + local_object_hash)
            self.debug("Uploaded content and downloaded content are not same.")
            return False
        return True

    def get_content(self, file_path):
        with open(file_path) as file_to_check:
            data = file_to_check.read()
        return data

    def get_hash(self, file_path):
        return hashlib.md5(self.get_content(file_path)).hexdigest()

    def create_file(self, size_in_kb, file_name="eutester-object"):
        temp_file = tempfile.NamedTemporaryFile(mode='w+b', prefix=file_name)
        self.temp_files.append(temp_file)
        temp_file.write(os.urandom(1024 * size_in_kb))
        return temp_file.name

    def concurrent_upload(self):
        self.debug("Creating object of " + str(self.args.object_size) + "KB")
        eu_file = open(self.create_file(self.args.object_size))
        thread_pool = []
        with ThreadPoolExecutor(max_workers=self.args.threads) as executor:
            for i in xrange(self.args.buckets):
                for j in xrange(self.args.objects):
                    thread_pool.append(executor.submit(self.put_get_check, bucket_name=self.bucket_names[i],
                                                       key_name=eu_file.name + str(j), eu_file=eu_file))

        for tp in thread_pool:
            try:
                if not tp.result():
                    self.fail("[CRITICAL] failed upload in thread")
            except Exception as e:
                self.fail("Found exception in thread-pool: " + e.message)

if __name__ == "__main__":
    testcase = OSGConcurrency()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["concurrent_upload"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list)
    exit(result)

# run testcases/cloud_user/s3/osg_concurrency_test.py --config /root/input/2b_tested.lst --password foobar --buckets 1 --objects 1 --threads 1 --object-size 10240 --mpu-threshold 0
# run testcases/cloud_user/s3/osg_concurrency_test.py --config /root/input/2b_tested.lst --password foobar --buckets 2 --objects 3 --object-size 10240 --threads 3 --mpu-threshold 5120