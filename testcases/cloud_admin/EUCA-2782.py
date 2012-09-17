import unittest
from eucaops import Eucaops
import argparse

class EUCA2782(unittest.TestCase):

    def setUp(self):
        try:
            ### Setup the cloud connection
            self.tester = Eucaops(credpath=args.credpath)
            ### Create a bucket in Walrus
            self.bucket_obj = self.tester.create_bucket('bucket_euca2782')
        except Exception, e:
            print 'Caught exception ' + str(e)
            self.fail('Failed to setup unit test for EUCA-2782 due to ' + str(e))

    def test_EUCA2782(self):
        ### Make a HEAD request against the bucket that was previous created and a key that does not exist
        response = self.tester.s3.make_request(method='HEAD', bucket=self.bucket_obj, key='key')

        ### Assert that the HTTP response has no message body and status is 404
        self.assertEqual(response.status, 404, 'Expected response status code to be 404, actual status code is ' + str(response.status))
        self.assertEqual(response.length, 0, 'Expected response length to be 0, actual length is ' + str(response.length))

    def tearDown(self):
        ### Tear down the bucket
        self.tester.delete_bucket(bucket=self.bucket_obj)
        self.tester=None

if __name__ == "__main__":
    ### Parse command line arguments and get the path to credentials
    parser = argparse.ArgumentParser(description='Unit test to verify fix for EUCA-2782')
    parser.add_argument('--credpath', dest='credpath', required=True, help='Path to folder containing credentials')
    args = parser.parse_args()

    ### Run the unit test
    suite = unittest.TestLoader().loadTestsFromTestCase(EUCA2782)
    unittest.TextTestRunner().run(suite)