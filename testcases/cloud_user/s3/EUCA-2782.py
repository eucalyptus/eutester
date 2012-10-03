__author__ = 'Swathi Gangisetty'

import unittest
from eucaops import Eucaops
import argparse

class EUCA2782(unittest.TestCase):

    def setUp(self):
        self.tester = eucaops

    def test_EUCA2782(self):
        ### Create a bucket in Walrus
        self.bucket_obj = self.tester.create_bucket('bucket_euca2782')

        ### Make a HEAD request against the bucket that was previously created and a key that does not exist
        response = self.tester.s3.make_request(method='HEAD', bucket=self.bucket_obj, key='key')

        ### Assert that the HTTP response has no message body and status is 404
        self.assertEqual(response.status, 404, 'Expected response status code to be 404, actual status code is ' + str(response.status))
        self.assertEqual(response.length, 0, 'Expected response length to be 0, actual length is ' + str(response.length))

        ### Delete the bucket
        self.tester.delete_bucket(bucket=self.bucket_obj)

    def test_EUCA2241(self):
        ### Create a bucket in Walrus
        self.bucket_obj = self.tester.s3.create_bucket('bucket_euca2241')

        ### GET a key that does not exist
        response = self.bucket_obj.get_key('key')

        ### Assert that the response is null
        self.assertEqual(response, None)

        ### Delete the bucket
        response = self.tester.s3.delete_bucket(bucket=self.bucket_obj)

        ### Assert that the response is null
        self.assertEqual(response, None)

        ### Make a HEAD request against the bucket that was deleted
        response = self.tester.s3.make_request(method='GET', bucket=self.bucket_obj)
        self.assertEqual(response.status, 404, 'Expected response status code to be 404, actual status code is ' + str(response.status))

    def tearDown(self):
        self.tester=None

if __name__ == "__main__":
    ### Parse command line arguments and get the path to credentials
    parser = argparse.ArgumentParser(description='Unit test to verify fix for EUCA-2782 and EUCA-2241')
    parser.add_argument('--credpath', dest='credpath', required=True, help='Path to folder containing credentials')
    args = parser.parse_args()

    try:
        ### Setup the cloud connection
        eucaops = Eucaops(credpath=args.credpath)
    except Exception, e:
        exit('Failed to establish connection to cloud due to: ' + str(e))

    ### Run the unit test
    suite = unittest.TestLoader().loadTestsFromTestCase(EUCA2782)
    unittest.TextTestRunner(verbosity=2).run(suite)

    eucaops=None