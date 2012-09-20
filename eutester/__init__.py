#!/usr/bin/python
# -*- coding: utf-8 -*-
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


__version__ = '0.0.3'

import re
import os
import boto
import random
import time
import string
import socket
import sys

from boto.ec2.regioninfo import RegionInfo
from boto.s3.connection import OrdinaryCallingFormat


import eulogger



class TimeoutFunctionException(Exception): 
    """Exception to raise on a timeout""" 
    pass 

EC2RegionData = {
    'us-east-1' : 'ec2.us-east-1.amazonaws.com',
    'us-west-1' : 'ec2.us-west-1.amazonaws.com',
    'eu-west-1' : 'ec2.eu-west-1.amazonaws.com',
    'ap-northeast-1' : 'ec2.ap-northeast-1.amazonaws.com',
    'ap-southeast-1' : 'ec2.ap-southeast-1.amazonaws.com'}

class Eutester(object):
    def __init__(self, credpath=None, aws_access_key_id=None, aws_secret_access_key = None, region=None, ec2_ip=None, s3_ip=None, boto_debug=0):
        """This class is intended to setup boto connections for the various services that the *ops classes will use.

        :param credpath: Path to a valid eucarc file.
        :param aws_access_key_id: Used in conjuction with aws_secret_access_key allows for creation of connections without needing a credpath.
        :param aws_secret_access_key: Used in conjuction with aws_access_key_id allows for creation of connections without needing a credpath.
        :param region: When connecting to Amazon EC2 allows you to point to a specific region.
        :param ec2_ip: Hostname or IP of the EC2 endpoint to connect to. Can be used in the absence of region.
        :param s3_ip: Hostname or IP of the S3 endpoint to connect to.
        :param boto_debug: Hostname or IP of the S3 endpoint to connect to.
        :rtype: :class:`eutester.Eutester` or ``None``
        :returns: A Eutester object with all connections that were able to be created. Currently EC2, S3, IAM, and STS.
        """
        ### Default values for configuration
        self.boto_debug = boto_debug
        self.credpath = credpath
        self.region = RegionInfo()
        
        ### Eutester logs
        if self.logger is None:
            self.logger = eulogger.Eulogger(identifier="EUTESTER")
            self.debug = self.logger.log.debug
            self.critical = self.logger.log.critical
            self.info = self.logger.log.info
        
        ### LOGS to keep for printing later
        self.fail_log = []
        self.running_log = self.logger.log

        ### Pull the access and secret keys from the eucarc or use the ones provided to the constructor
        if self.credpath is not None:
            self.debug("Extracting keys from " + self.credpath)         
            self.aws_access_key_id = self.get_access_key()
            self.aws_secret_access_key = self.get_secret_key()
        else:
            self.aws_access_key_id = aws_access_key_id
            self.aws_secret_access_key = aws_secret_access_key
        
        ### If you have credentials for the boto connections, create them
        if (self.aws_access_key_id is not None) and (self.aws_secret_access_key != None):
            if not boto.config.has_section('Boto'):
                boto.config.add_section('Boto')
            boto.config.set('Boto', 'num_retries', '2')
            self.setup_boto_connections(region=region,ec2_ip=ec2_ip,s3_ip=s3_ip)

    def setup_boto_connections(self, region=None, aws_access_key_id=None, aws_secret_access_key=None, ec2_ip=None, s3_ip=None, is_secure=False):
        
        if aws_access_key_id is None:
            aws_access_key_id = self.aws_access_key_id
        if aws_secret_access_key is None:
            aws_secret_access_key = self.aws_secret_access_key     
        port = 443
        service_path = "/"
        APIVersion = '2009-11-30'

        if region is not None:
            self.debug("Check region: " + str(region))        
            try:
                self.region.endpoint = EC2RegionData[region]
            except KeyError:
                raise Exception( 'Unknown region: %s' % region)
        
        if not self.region.endpoint:
            #self.get_connection_details()
            self.region.name = 'eucalyptus'
            if ec2_ip is None:
                self.region.endpoint = self.get_ec2_ip()       
            else:
                self.region.endpoint = ec2_ip
            port = 8773
            service_path="/services/Eucalyptus"
            
        try:    
            self.debug("Attempting to create ec2 connection to " + self.region.endpoint)
            self.ec2 = boto.connect_ec2(aws_access_key_id=aws_access_key_id,
                                    aws_secret_access_key=aws_secret_access_key,
                                    is_secure=is_secure,
                                    debug=self.boto_debug,
                                    region=self.region,
                                    port=port,
                                    path=service_path,
                                    api_version=APIVersion)
        except Exception, e:
            self.critical("Was unable to create ec2 connection because of exception: " + str(e))

        try:
            if s3_ip is not None:
                walrus_endpoint = s3_ip
            else:
                walrus_endpoint = self.get_s3_ip()
                
            self.debug("Attempting to create S3 connection to " + walrus_endpoint)
            self.s3 = boto.connect_s3(aws_access_key_id=aws_access_key_id,
                                                  aws_secret_access_key=aws_secret_access_key,
                                                  is_secure=False,
                                                  host= walrus_endpoint,
                                                  port=8773,
                                                  path="/services/Walrus",
                                                  calling_format=OrdinaryCallingFormat(),
                                                  debug=self.boto_debug)
        except Exception, e:
            self.critical("Was unable to create S3 connection because of exception: " + str(e))
        
        try:    
            self.euare = boto.connect_iam(aws_access_key_id=aws_access_key_id,
                                                  aws_secret_access_key=aws_secret_access_key,
                                                  is_secure=False,
                                                  host=self.get_ec2_ip(),
                                                  port=8773, 
                                                  path="/services/Euare",
                                                  debug=self.boto_debug)
        except Exception, e:
            self.critical("Was unable to create IAM connection because of exception: " + str(e))

        try:
            self.tokens = boto.connect_sts(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region=self.region,
                port=8773,
                path="/services/Tokens",
                is_secure=False,
                debug=self.boto_debug)

        except Exception, e:
            self.critical("Was unable to create STS connection because of exception: " + str(e))

    def get_access_key(self):
        """Parse the eucarc for the EC2_ACCESS_KEY"""
        return self.parse_eucarc("EC2_ACCESS_KEY")   
    
    def get_secret_key(self):
        """Parse the eucarc for the EC2_SECRET_KEY"""
        return self.parse_eucarc("EC2_SECRET_KEY")
    
    def get_account_id(self):
        """Parse the eucarc for the EC2_ACCOUNT_NUMBER"""
        return self.parse_eucarc("EC2_ACCOUNT_NUMBER")
    
    def get_user_id(self):
        """Parse the eucarc for the EC2_ACCOUNT_NUMBER"""
        return self.parse_eucarc("EC2_USER_ID")
        
    def parse_eucarc(self, field):
        with open( self.credpath + "/eucarc") as eucarc: 
            for line in eucarc.readlines():
                if re.search(field, line):
                    return line.split("=")[1].strip().strip("'")
            raise Exception("Unable to find " +  field + " id in eucarc")
    
    def get_s3_ip(self):
        """Parse the eucarc for the S3_URL"""
        walrus_url = self.parse_eucarc("S3_URL")
        return walrus_url.split("/")[2].split(":")[0]
    
    def get_ec2_ip(self):
        """Parse the eucarc for the EC2_URL"""
        ec2_url = self.parse_eucarc("EC2_URL")
        return ec2_url.split("/")[2].split(":")[0]        
    
    def handle_timeout(self, signum, frame): 
        raise TimeoutFunctionException()

    def local(self, cmd):
        """ Run a command locally on the tester"""
        std_out_return = os.popen(cmd).readlines()
        return std_out_return
    
    def found(self, command, regex):
        """ Returns a Boolean of whether the result of the command contains the regex
        """
        result = self.local(command)
        for line in result:
            found = re.search(regex,line)
            if found:
                return True
        return False
    
    def ping(self, address, poll_count = 10):
        """
        Ping an IP and poll_count times (Default = 10)
        address      Hostname to ping
        poll_count   The amount of times to try to ping the hostname iwth 2 second gaps in between
        """
        if re.search("0.0.0.0", address): 
            self.critical("Address is all 0s and will not be able to ping it") 
            return False
        self.debug("Attempting to ping " + address)
        while poll_count > 0:
            poll_count -= 1 
            if self.found("ping -c 1 " + address, "1.*1.*received"):
                self.debug("Was able to ping address")
                return True
            if poll_count == 0:
                self.critical("Was unable to ping address")
                return False
            self.debug("Ping unsuccessful retrying in 2 seconds " + str(poll_count) + " more times")
            self.sleep(2)    
    
    def scan_port_range(self, ip, start, stop, timeout=1, tcp=True):
        '''
        Attempts to connect to ports, returns list of ports which accepted a connection
        '''
        ret = []
        for x in xrange(start,stop+1):
            try:
                sys.stdout.write("\r\x1b[K"+str('scanning:'+str(x)))
                sys.stdout.flush()
                self.test_port_status(ip, x, timeout=timeout,tcp=tcp, verbose=False)
                ret.append(x)
            except socket.error, se:
                pass
        return ret
    
    def test_port_status(self, ip, port, timeout=5, tcp=True, verbose=True):
        '''
        Attempts to connect to tcp port at ip:port within timeout seconds
        '''
        if verbose:
            debug = self.debug
        else:
            debug = lambda msg: None
        debug('test_port_status, ip:'+str(ip)+', port:'+str(port)+', TCP:'+str(tcp))
        if tcp:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        s.settimeout(timeout)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            if tcp:
                s.connect((ip, port))
            else:
                s.sendto("--TEST LINE--", (ip, port))
                recv, svr = s.recvfrom(255)
        except socket.error, se:
            debug('test_port_status failed socket error:'+str(se[0]))
            #handle specific errors here, for now just for debug...
            ecode=se[0]
            if ecode == socket.errno.ECONNREFUSED:
                debug("test_port_status: Connection Refused")
            if ecode == socket.errno.ENETUNREACH:
                debug("test_port_status: Network unreachable")
            if ecode == socket.errno.ETIMEDOUT or ecode == "timed out":
                debug("test_port_status: Connect to "+str(ip)+":" +str(port)+ " timed out")
            raise se
        except socket.timeout, st:
            debug('test_port_status failed socket timeout')
            raise st
        finally:
            s.settimeout(None)
            s.close()
        debug('test_port_status, success')
    
    def grep(self, string,list):
        """ Remove the strings from the list that do not match the regex string"""
        expr = re.compile(string)
        return filter(expr.search,list)
        
    def diff(self, list1, list2):
        """Return the diff of the two lists"""
        return list(set(list1)-set(list2))
    
    def fail(self, message):
        self.critical(message)
        self.fail_log.append(message)
        self.fail_count += 1
        if self.exit_on_fail == 1:
            raise Exception("Test step failed: "+str(message))
        else:
            return 0 
    
    def clear_fail_log(self):
        self.fail_log = []
        return
    
    def get_exectuion_time(self):
        """Returns the total execution time since the instantiation of the Eutester object"""
        return time.time() - self.start_time
       
    def clear_fail_count(self):
        """ The counter for keeping track of all the errors """
        self.fail_count = 0
        
    def sleep(self, seconds=1):
        """Convinience function for time.sleep()"""
        self.debug("Sleeping for " + str(seconds) + " seconds")
        time.sleep(seconds)
    
    def id_generator(self, size=6, chars=string.ascii_uppercase + string.ascii_lowercase  + string.digits ):
        """Returns a string of size with random charachters from the chars array.
             size    Size of string to return
             chars   Array of characters to use in generation of the string
        """
        return ''.join(random.choice(chars) for x in range(size))
        
    def __str__(self):
        """
        Prints informations about configuration of Eucateser as configuration file,
        how many errors, the path of the Eucalyptus, and the path of the user credentials
        """
        s  = "+++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        s += "+" + "Eucateser Configuration" + "\n"
        s += "+" + "+++++++++++++++++++++++++++++++++++++++++++++++\n"
        s += "+" + "Config File: " + self.config_file +"\n"
        s += "+" + "Fail Count: " +  str(self.fail_count) +"\n"
        s += "+" + "Eucalyptus Path: " +  str(self.eucapath) +"\n"
        s += "+" + "Credential Path: " +  str(self.credpath) +"\n"
        s += "+++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        return s

