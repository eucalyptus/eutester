import unittest
from eucaops import Eucaops
import argparse

class EUCA2782(unittest.TestCase):

    def setUp(self):
        try:
            self.tester = Eucaops(credpath=args.credpath)
            self.bucket_obj = self.tester.create_bucket('bucket_euca2782')
        except Exception, e:
            print 'Caught exception ' + str(e)
            self.fail('Failed to setup unit test for EUCA-2782 due to ' + str(e))

    def test_EUCA2782(self):
        response = self.tester.s3.make_request(method='HEAD', bucket=self.bucket_obj, key='key')

        self.assertEqual(response.status, 404, 'Expected response status code to be 404, actual status code is ' + str(response.status))
        self.assertEqual(response.length, 0, 'Expected response length to be 0, actual length is ' + str(response.length))

    def tearDown(self):
        self.tester.delete_bucket(bucket=self.bucket_obj)
        self.tester=None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Unit test to verify fix for EUCA-2782')
    parser.add_argument('--credpath', dest='credpath', required=True, help='Path to folder containing credentials')
    args = parser.parse_args()
    suite = unittest.TestLoader().loadTestsFromTestCase(EUCA2782)
    unittest.TextTestRunner(verbosity=1).run(suite)