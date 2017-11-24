#!/usr/bin/env python
"""
Purpose:  Testcase to demonstrate and confirm that AWS
          Signature 4 is supported by Eucalyptus.

Author:   Harold Spencer Jr. (https://github.com/hspencer77)
"""
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
import datetime
import hashlib
import hmac
import requests
import xml.dom.minidom


class AutoScalingSigV4Test(EutesterTestCase):
    def __init__(self, extra_args=None):
        """
        Function to initialize testcase
        for AWS SigV4 against AutoScaling Service

        param: ---credpath: path to directory
               location of Eucalyptus credentials
        """
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument('--clean_on_exit',
                                 action='store_true', default=True,
                                 help=('Boolean, used to flag whether to'
                                       + ' run clean up method after '
                                       + 'running test list'))
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()

        self.tester = Eucaops(credpath=self.args.credpath,
                              config_file=self.args.config,
                              password=self.args.password)

        # Gather endpoint information for each region
        self.regions = []
        for region in self.tester.ec2.get_all_regions():
            endpoint = str(region.endpoint)
            as_endpoint = endpoint.replace('compute',
                                            'autoscaling')
            region_info = {'name': str(region.name),
                           'endpoint': as_endpoint}
            self.regions.append(region_info)

    @classmethod
    def assertEquals(cls, x, y, msg):
        """
        Function to compare to values.

        param: x:  first value to compare
        param: y:  second value to compare
        param msg: additional message to add in case of error
        """
        assert x == y, str(x) + ' is not equal to ' + str(y) + ': ' + msg

    def clean_method(self):
        # Function to clean up artifacts
        for region in self.regions:
            del region

    def request_params(self):
        """
        Function to return default request
        parameters.
        """
        method = 'GET'
        service = 'autoscaling'
        request_parameters = 'Action=DescribeAutoScalingGroups&Version=2011-01-01'
        return (method, service, request_parameters)

    def sign(self, key, msg):
        """
        Function to help create an signing key (HMAC).
        For more information refer to
        http://docs.aws.amazon.com/general/latest/
        gr/sigv4-calculate-signature.html

        param: key: key to use for signing
        param: msg: sting to sign
        """
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    def getSignatureKey(self, key, datestamp, region, service):
        """
        Function to generate signing key. For more information, refer
        to http://docs.aws.amazon.com/general/latest/
        gr/sigv4-calculate-signature.html.

        param: key: AWS secret key
        param: datestamp: request date for generating signed date element
        param: region: region for generating signed region element
        param: service: service for generating signed service element
        """
        sigDate = self.sign(('AWS4' + key).encode('utf-8'), datestamp)
        sigRegion = self.sign(sigDate, region)
        sigService = self.sign(sigRegion, service)
        sigSigning = self.sign(sigService, 'aws4_request')
        return sigSigning

    def createCanonicalRequest(self, method, request_parameters,
                               host, amzdate):
        """
        Function to create canonical request.  For more information,
        refer to http://docs.aws.amazon.com/general/latest/
        gr/sigv4-create-canonical-request.html

        param: method: HTTP request method
        param: request_parameters: parameters for canonical
               query string
        param: host: service endpoint
        param: amzdate: date used to create the signature
        """
        canonical_uri = '/'
        canonical_querystring = request_parameters
        canonical_headers = ('host:' + host + '\n'
                             + 'x-amz-date:'
                             + amzdate + '\n')
        signed_headers = 'host;x-amz-date'
        payload_hash = hashlib.sha256('').hexdigest()
        canonical_request = (method + '\n'
                             + canonical_uri + '\n'
                             + canonical_querystring + '\n'
                             + canonical_headers + '\n'
                             + signed_headers + '\n'
                             + payload_hash)
        return canonical_request

    def createStringtoSign(self, datestamp, region,
                           service, amzdate, canonical_request):
        """
        Function to create string to sign for SigV4. For more
        information refer to http://docs.aws.amazon.com/general/
        latest/gr/sigv4-create-string-to-sign.html.

        param: datestamp: request date
        param: region:  region name
        param: service: AWS Service
        param: amzdate: x-amz-date header value
        param: canonical_request: canonical request to be
               added to the meta information in the request
        """
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = (datestamp + '/' + region
                            + '/' + service + '/'
                            + 'aws4_request')
        string_to_sign = (algorithm + '\n'
                          + amzdate + '\n'
                          + credential_scope + '\n'
                          + hashlib.sha256(canonical_request).hexdigest())
        return string_to_sign

    def createAuthHeader(self, datestamp, region, signature, service):
        """
        Function to create Authorization header for the Service request.
        For more information refer to http://docs.aws.amazon.com/general/
        latest/gr/sigv4-add-signature-to-request.html.

        param: datestamp: request date
        param: region: region name
        param: signature: signature to add to header
        param: service: AWS Service
        """
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = (datestamp + '/'
                            + region + '/'
                            + service + '/'
                            + 'aws4_request')
        signed_headers = 'host;x-amz-date'
        authorization_header = (algorithm + ' '
                                + 'Credential='
                                + self.tester.ec2.aws_access_key_id + '/'
                                + credential_scope + ', '
                                + 'SignedHeaders=' + signed_headers + ', '
                                + 'Signature=' + signature)
        return authorization_header

    def sigV4Test(self):
        """
        Function to execute testcase that deomnstrates
        support for AWS signature 4 for AutoScaling Service.
        For more information please refer to
        http://docs.aws.amazon.com/general/
        latest/gr/signature-version-4.html
        """
        for region in self.regions:
            # Grab information from request parameters
            (method, service, request_parameters) = self.request_params()
            # Strip http:// or https:// from endpoint
            host = region['endpoint'].strip('http://https://')

            # Define amzdate and datestamp off current time
            t = datetime.datetime.utcnow()
            amzdate = t.strftime('%Y%m%dT%H%M%SZ')
            datestamp = t.strftime('%Y%m%d')

            # Create canonical request
            canonical_request = self.createCanonicalRequest(method,
                                                            request_parameters,
                                                            host,
                                                            amzdate)
            # Create sting to sign
            string_to_sign = self.createStringtoSign(datestamp,
                                                     region['name'],
                                                     service,
                                                     amzdate,
                                                     canonical_request)
            # Create signing key for signature
            signing_key = self.getSignatureKey(
                              self.tester.ec2.aws_secret_access_key,
                              datestamp,
                              region['name'],
                              service)
            # Calculate the signature
            signature = hmac.new(signing_key,
                                 (string_to_sign).encode('utf-8'),
                                 hashlib.sha256).hexdigest()
            # Add signing information to Authorization Header
            authorization_header = self.createAuthHeader(datestamp,
                                                         region['name'],
                                                         signature,
                                                         service)
            headers = {'x-amz-date': amzdate,
                       'Authorization': authorization_header}
            request_url = region['endpoint'] + '?' + request_parameters
            self.tester.info("\nAWS SigV4 Compute Test "
                             + "against " + region['name']
                             + " endpoint")
            self.tester.info("\nBEGIN REQUEST +++++++++++++++++++++++++++++++")
            self.tester.info("Request URL = " + request_url)
            # Perform request
            try:
                sigv4_request = requests.get(request_url,
                                             headers=headers,
                                             timeout=5)
            except requests.exceptions.ConnectionError:
                self.tester.debug("Connection error occurred using "
                                  + "endpoint "
                                  + region['endpoint'])
            except requests.exceptions.Timeout:
                self.tester.debug("Connection timeout occurred using "
                                  + "endpoint "
                                  + region['endpoint'])
            except requests.exceptions.RequestException as e:
                self.tester.debug("Exception occurred "
                                  + "during 'GET' request using "
                                  + request_url
                                  + ": " + e.message)
                raise e
            # Process response into readable XML
            sigv4_xml_resp = xml.dom.minidom.parseString(sigv4_request.text)
            sigv4_response = sigv4_xml_resp.toprettyxml()
            self.tester.info("\nRESPONSE ++++++++++++++++++++++++++++++++++++")
            self.tester.info("Response code: {code}\n{response}".format(
                              code=sigv4_request.status_code,
                              response=sigv4_response))
            self.assertEquals(sigv4_request.status_code,
                              200,
                              "AWS SigV4 Request Failed.")

if __name__ == "__main__":
    # Define AutoScalingSigV4Test testcase
    testcase = AutoScalingSigV4Test()
    list = ['sigV4Test']
    unit_list = []
    for test in list:
        unit_list.append(testcase.create_testunit_by_name(test))
    # Execute testcase
    result = testcase.run_test_case_list(
                 unit_list,
                 clean_on_exit=testcase.args.clean_on_exit)
    exit(result)
