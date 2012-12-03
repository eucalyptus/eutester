__author__ = 'Swathi Gangisetty'

import unittest
from eucaops import Eucaops
import argparse

key_with_star_name = 'special characters%unravelled_bigtime/abc*'
key_with_dollar_name = 'special characters%unravelled_bigtime/abc$'
key_with_exclamation_name = 'special characters%unravelled_bigtime/abc!'
key_with_percent_name = 'special characters%unravelled_bigtime/abc%'
key_with_underscore_name = 'special characters%unravelled_bigtime/abc_'
key_with_backtick_name = 'special characters%unravelled_bigtime/abc~'
key_with_atrate_name = 'special characters%unravelled_bigtime/abc@'
key_with_pound_name = 'special characters%unravelled_bigtime/abc#'
key_with_caret_name = 'special characters%unravelled_bigtime/abc^'
key_with_ampersand_name = 'special characters%unravelled_bigtime/abc&'
key_with_leftbrace_name = 'special characters%unravelled_bigtime/abc('
key_with_rightbrace_name = 'special characters%unravelled_bigtime/abc)'

class EUCA3453(unittest.TestCase):

    def setUp(self):
        ### Create a bucket in Walrus
        self.tester = eucaops
        self.bucket_obj = self.tester.create_bucket('bucket_euca3453')

    def test_1(self):
        ### Create keys and set content
        key_with_star = self.bucket_obj.new_key(key_name=key_with_star_name)
        key_with_star.set_contents_from_string('key with star')

        key_with_dollar = self.bucket_obj.new_key(key_name=key_with_dollar_name)
        key_with_dollar.set_contents_from_string('key with dollar')

        ### Get keys and check content
        key_with_star = self.bucket_obj.get_key(key_name=key_with_star_name)
        self.assertEqual(key_with_star.read(), 'key with star')

        key_with_dollar = self.bucket_obj.get_key(key_name=key_with_dollar_name)
        self.assertEqual(key_with_dollar.read(), 'key with dollar')

        ### Delete keys
        self.bucket_obj.delete_key(key_name=key_with_star_name)
        self.bucket_obj.delete_key(key_name=key_with_dollar_name)

    def test_2(self):
        ### Create keys and set content
        key_with_exclamation = self.bucket_obj.new_key(key_name=key_with_exclamation_name)
        key_with_exclamation.set_contents_from_string('key with exclamation')

        key_with_percent = self.bucket_obj.new_key(key_name=key_with_percent_name)
        key_with_percent.set_contents_from_string('key with percent')

        ### Get keys and check content
        key_with_exclamation = self.bucket_obj.get_key(key_name=key_with_exclamation_name)
        self.assertEqual(key_with_exclamation.read(), 'key with exclamation')

        key_with_percent = self.bucket_obj.get_key(key_name=key_with_percent_name)
        self.assertEqual(key_with_percent.read(), 'key with percent')

        ### Delete keys
        self.bucket_obj.delete_key(key_name=key_with_exclamation_name)
        self.bucket_obj.delete_key(key_name=key_with_percent_name)

    def test_3(self):
        ### Create keys and set content
        key_with_underscore = self.bucket_obj.new_key(key_name=key_with_underscore_name)
        key_with_underscore.set_contents_from_string('key with underscore')

        key_with_backtick = self.bucket_obj.new_key(key_name=key_with_backtick_name)
        key_with_backtick.set_contents_from_string('key with backtick')

        ### Get keys and check content
        key_with_underscore = self.bucket_obj.get_key(key_name=key_with_underscore_name)
        self.assertEqual(key_with_underscore.read(), 'key with underscore')

        key_with_backtick = self.bucket_obj.get_key(key_name=key_with_backtick_name)
        self.assertEqual(key_with_backtick.read(), 'key with backtick')

        ### Delete keys
        self.bucket_obj.delete_key(key_name=key_with_underscore_name)
        self.bucket_obj.delete_key(key_name=key_with_backtick_name)

    def test_4(self):
        ### Create keys and set content
        key_with_atrate = self.bucket_obj.new_key(key_name=key_with_atrate_name)
        key_with_atrate.set_contents_from_string('key with at rate')

        key_with_pound = self.bucket_obj.new_key(key_name=key_with_pound_name)
        key_with_pound.set_contents_from_string('key with pound')

        ### Get keys and check content
        key_with_atrate = self.bucket_obj.get_key(key_name=key_with_atrate_name)
        self.assertEqual(key_with_atrate.read(), 'key with at rate')

        key_with_pound = self.bucket_obj.get_key(key_name=key_with_pound_name)
        self.assertEqual(key_with_pound.read(), 'key with pound')

        ### Delete keys
        self.bucket_obj.delete_key(key_name=key_with_atrate_name)
        self.bucket_obj.delete_key(key_name=key_with_pound_name)

    def test_5(self):
        ### Create keys and set content
        key_with_caret = self.bucket_obj.new_key(key_name=key_with_caret_name)
        key_with_caret.set_contents_from_string('key with caret')

        key_with_ampersand = self.bucket_obj.new_key(key_name=key_with_ampersand_name)
        key_with_ampersand.set_contents_from_string('key with ampersand')

        ### Get keys and check content
        key_with_caret = self.bucket_obj.get_key(key_name=key_with_caret_name)
        self.assertEqual(key_with_caret.read(), 'key with caret')

        key_with_ampersand = self.bucket_obj.get_key(key_name=key_with_ampersand_name)
        self.assertEqual(key_with_ampersand.read(), 'key with ampersand')

        ### Delete keys
        self.bucket_obj.delete_key(key_name=key_with_caret_name)
        self.bucket_obj.delete_key(key_name=key_with_ampersand_name)

    def test_6(self):
        ### Create keys and set content
        key_with_leftbrace = self.bucket_obj.new_key(key_name=key_with_leftbrace_name)
        key_with_leftbrace.set_contents_from_string('key with left brace')

        key_with_rightbrace = self.bucket_obj.new_key(key_name=key_with_rightbrace_name)
        key_with_rightbrace.set_contents_from_string('key with right brace')

        ### Get keys and check content
        key_with_leftbrace = self.bucket_obj.get_key(key_name=key_with_leftbrace_name)
        self.assertEqual(key_with_leftbrace.read(), 'key with left brace')

        key_with_rightbrace = self.bucket_obj.get_key(key_name=key_with_rightbrace_name)
        self.assertEqual(key_with_rightbrace.read(), 'key with right brace')

        ### Delete keys
        self.bucket_obj.delete_key(key_name=key_with_leftbrace_name)
        self.bucket_obj.delete_key(key_name=key_with_rightbrace_name)

    def test_all(self):
        ### Create keys and set content
        key_with_star = self.bucket_obj.new_key(key_name=key_with_star_name)
        key_with_star.set_contents_from_string('key with star')

        key_with_leftbrace = self.bucket_obj.new_key(key_name=key_with_leftbrace_name)
        key_with_leftbrace.set_contents_from_string('key with left brace')

        key_with_dollar = self.bucket_obj.new_key(key_name=key_with_dollar_name)
        key_with_dollar.set_contents_from_string('key with dollar')

        key_with_exclamation = self.bucket_obj.new_key(key_name=key_with_exclamation_name)
        key_with_exclamation.set_contents_from_string('key with exclamation')

        key_with_backtick = self.bucket_obj.new_key(key_name=key_with_backtick_name)
        key_with_backtick.set_contents_from_string('key with backtick')

        key_with_atrate = self.bucket_obj.new_key(key_name=key_with_atrate_name)
        key_with_atrate.set_contents_from_string('key with at rate')

        key_with_ampersand = self.bucket_obj.new_key(key_name=key_with_ampersand_name)
        key_with_ampersand.set_contents_from_string('key with ampersand')

        key_with_rightbrace = self.bucket_obj.new_key(key_name=key_with_rightbrace_name)
        key_with_rightbrace.set_contents_from_string('key with right brace')

        key_with_pound = self.bucket_obj.new_key(key_name=key_with_pound_name)
        key_with_pound.set_contents_from_string('key with pound')

        key_with_caret = self.bucket_obj.new_key(key_name=key_with_caret_name)
        key_with_caret.set_contents_from_string('key with caret')

        key_with_percent = self.bucket_obj.new_key(key_name=key_with_percent_name)
        key_with_percent.set_contents_from_string('key with percent')

        key_with_underscore = self.bucket_obj.new_key(key_name=key_with_underscore_name)
        key_with_underscore.set_contents_from_string('key with underscore')

        ### Get keys and check content
        key_with_star = self.bucket_obj.get_key(key_name=key_with_star_name)
        self.assertEqual(key_with_star.read(), 'key with star')

        key_with_dollar = self.bucket_obj.get_key(key_name=key_with_dollar_name)
        self.assertEqual(key_with_dollar.read(), 'key with dollar')

        key_with_exclamation = self.bucket_obj.get_key(key_name=key_with_exclamation_name)
        self.assertEqual(key_with_exclamation.read(), 'key with exclamation')

        key_with_percent = self.bucket_obj.get_key(key_name=key_with_percent_name)
        self.assertEqual(key_with_percent.read(), 'key with percent')

        key_with_underscore = self.bucket_obj.get_key(key_name=key_with_underscore_name)
        self.assertEqual(key_with_underscore.read(), 'key with underscore')

        key_with_backtick = self.bucket_obj.get_key(key_name=key_with_backtick_name)
        self.assertEqual(key_with_backtick.read(), 'key with backtick')

        key_with_atrate = self.bucket_obj.get_key(key_name=key_with_atrate_name)
        self.assertEqual(key_with_atrate.read(), 'key with at rate')

        key_with_pound = self.bucket_obj.get_key(key_name=key_with_pound_name)
        self.assertEqual(key_with_pound.read(), 'key with pound')

        key_with_caret = self.bucket_obj.get_key(key_name=key_with_caret_name)
        self.assertEqual(key_with_caret.read(), 'key with caret')

        key_with_ampersand = self.bucket_obj.get_key(key_name=key_with_ampersand_name)
        self.assertEqual(key_with_ampersand.read(), 'key with ampersand')

        key_with_leftbrace = self.bucket_obj.get_key(key_name=key_with_leftbrace_name)
        self.assertEqual(key_with_leftbrace.read(), 'key with left brace')

        key_with_rightbrace = self.bucket_obj.get_key(key_name=key_with_rightbrace_name)
        self.assertEqual(key_with_rightbrace.read(), 'key with right brace')

        ### Delete keys
        self.bucket_obj.delete_key(key_name=key_with_star_name)
        self.bucket_obj.delete_key(key_name=key_with_dollar_name)
        self.bucket_obj.delete_key(key_name=key_with_exclamation_name)
        self.bucket_obj.delete_key(key_name=key_with_percent_name)
        self.bucket_obj.delete_key(key_name=key_with_underscore_name)
        self.bucket_obj.delete_key(key_name=key_with_backtick_name)
        self.bucket_obj.delete_key(key_name=key_with_atrate_name)
        self.bucket_obj.delete_key(key_name=key_with_pound_name)
        self.bucket_obj.delete_key(key_name=key_with_caret_name)
        self.bucket_obj.delete_key(key_name=key_with_ampersand_name)
        self.bucket_obj.delete_key(key_name=key_with_leftbrace_name)
        self.bucket_obj.delete_key(key_name=key_with_rightbrace_name)

    def tearDown(self):
        ### Tear down the bucket
        self.tester.delete_bucket(bucket=self.bucket_obj)
        self.tester=None

if __name__ == "__main__":
    ### Parse command line arguments and get the path to credentials
    parser = argparse.ArgumentParser(description='Unit tests to verify: fix for EUCA-3453, and handling of special '
                                                 'characters in Walrus object names')
    parser.add_argument('--credpath', dest='credpath', required=True, help='Path to folder containing credentials')
    args = parser.parse_args()

    try:
        ### Setup the cloud connection
        eucaops = Eucaops(credpath=args.credpath)
    except Exception, e:
        exit('Failed to establish connection to cloud due to: ' + str(e))

    ### Run the unit test
    suite = unittest.TestLoader().loadTestsFromTestCase(EUCA3453)
    unittest.TextTestRunner(verbosity=2).run(suite)

    eucaops=None
