#!/usr/bin/env python
import time
from concurrent.futures import ThreadPoolExecutor
from eucaops import Eucaops
from eucaops import S3ops
from eutester.eutestcase import EutesterTestCase

class WalrusConcurrent(EutesterTestCase):
    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("-n", "--number", type=int, default=100)
        self.parser.add_argument("-c", "--concurrent", type=int, default=10)
        self.parser.add_argument("-s", "--size", type=int, default=1024)
        self.get_args()
        # Setup basic eutester object
        if self.args.region:
            self.tester = S3ops( credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops( credpath=self.args.credpath, config_file=self.args.config,password=self.args.password)
        self.start = time.time()
        self.bucket_name = "concurrency-" + str(int(self.start))
        self.tester.create_bucket(self.bucket_name)

    def clean_method(self):
        self.tester.clear_bucket(self.bucket_name)

    def Concurrent(self):
        key_payload = self.tester.id_generator(self.args.size)
        thread_count = self.args.number
        thread_pool = []
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
                for i in xrange(thread_count):
                        thread_pool.append(executor.submit(self.tester.upload_object, bucket_name=self.bucket_name, key_name="test" + str(i), contents=key_payload))
        end = time.time()
        total = end - self.start
        self.tester.debug("\nExecution time: {0}\n# of Objects: {1}\nObject Size: {2}B\nConcurrency Level of {3}".format(
                            total, self.args.number, self.args.size, self.args.concurrent))
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
                for object in thread_pool:
                        thread_pool.append(executor.submit(self.tester.delete_object, object))


if __name__ == "__main__":
    testcase = WalrusConcurrent()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["Concurrent"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list)
    exit(result)