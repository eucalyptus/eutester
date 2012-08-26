#!/usr/bin/env python
# Copyright 2011-2012 Eucalyptus Systems, Inc.
#
# Redistribution and use of this software in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
#   Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from eucaops import Eucaops
from xml.etree import ElementTree
from eutester import xmlrunner
import argparse
import unittest
import httplib
import base64

arg_credpath = None

class StsUI(unittest.TestCase):
    """
    Tests for STS UI Authentication.

    Available tests are:
      - testIssueToken - basic test for token issuance
    """
    account_name = 'test-sts-ui-account'
    admin_password = 'password'

    def setUp(self):
        self.tester = Eucaops( credpath=arg_credpath )
        self.createTestUser()

    def tearDown(self):
        self.deleteTestUser()
        self.tester = None

    def testIssueToken(self):
        """
        Test basic token issuance
        """
        ip = self.tester.tokens.region.endpoint
        port = self.tester.tokens.port
        path = self.tester.tokens.path
        api_version = self.tester.tokens.APIVersion
        url_template = '{0}?Version={1}&Action=GetSessionToken'
        sts_url = url_template.format( path, api_version )

        account = self.account_name
        username = 'admin'
        password = self.admin_password
        user_b64 = base64.b64encode( username )
        account_b64 = base64.b64encode( account )
        user_account = '{0}@{1}'.format( user_b64, account_b64 )
        creds = '{0}:{1}'.format( user_account, password )
        basic_header = "Basic {0}".format( base64.b64encode( creds.encode('utf8') ) )

        headers = {
            "Authorization": basic_header
        }
        conn = httplib.HTTPConnection( ip, port=port, timeout=30000 )
        conn.request( "GET", sts_url, headers=headers )
        response = conn.getresponse()

        self.assertEquals( 200, response.status, msg='Get token failed, bad HTTP status code: {0}'.format(response.status) )

        data = response.read()
        response.close()
        conn.close()

        rootElement = ElementTree.fromstring( data )
        resultElement = self.childElement( rootElement, 'GetSessionTokenResult' )
        credentialsElement = self.childElement( resultElement, 'Credentials')
        accessKeyIdElement = self.childElement( credentialsElement, 'AccessKeyId')
        secretAccessKeyElement = self.childElement( credentialsElement, 'SecretAccessKey')
        sessionTokenElement = self.childElement( credentialsElement, 'SessionToken')
        expirationElement = self.childElement( credentialsElement, 'Expiration')
        self.assertTrue( len( accessKeyIdElement.text ) > 0, msg='Missing accessKeyId' )
        self.assertTrue( len( secretAccessKeyElement.text ) > 0, msg='Missing secretAccessKey' )
        self.assertTrue( len( sessionTokenElement.text ) > 0, msg='Missing sessionToken' )
        self.assertTrue( len( expirationElement.text ) > 0, msg='Missing expiration' )
        self.tester.debug( "Got session token with access key: " + accessKeyIdElement.text )
        self.tester.debug( "Got session token with expiration: " + expirationElement.text )

    def childElement( self, parentElement, name ):
        childElement = parentElement.find( '{{https://sts.amazonaws.com/doc/2011-06-15/}}{0}'.format( name ) )
        self.assertTrue( childElement is not None, msg='STS response invalid, could not find {0}'.format( name ) )
        return childElement

    def createTestUser(self):
        self.tester.create_account(self.account_name)
        self.tester.euare.get_response('UpdateLoginProfile', {
            'DelegateAccount': self.account_name,
            'UserName': 'admin',
            'Password': self.admin_password
        })
        self.tester.euare.get_response('CreateAccessKey',  {
            'DelegateAccount': self.account_name,
            'UserName': 'admin',
        })

    def deleteTestUser(self):
        self.tester.delete_account(self.account_name,recursive=True)


if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(prog='ststest.py',
        version='Test Case [ststest.py] Version 0.1',
        description='''Test token service functionality and features
                       on a Eucalyptus Cloud.''',
        usage="%(prog)s --credpath=<path to creds> [--xml] [--tests=test1,..testN]")
    parser.add_argument('--credpath',
        help="path to user credentials", default=".eucarc")
    parser.add_argument('--xml',
        help="to provide JUnit style XML output", action="store_true", default=False)
    parser.add_argument('--tests', nargs='+',
        help="test cases to be executed",
        default= ['testIssueToken'])
    args = parser.parse_args()
    arg_credpath = args.credpath
    for test in args.tests:
        if args.xml:
            file = open("test-" + test + "result.xml", "w")
            result = xmlrunner.XMLTestRunner(file).run(StsUI(test))
        else:
            result = unittest.TextTestRunner(verbosity=2).run(StsUI(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)