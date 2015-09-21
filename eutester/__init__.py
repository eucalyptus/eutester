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

__version__ = '0.0.10'

import re
import os
import random
import time
import string
import socket
import sys
import traceback
import StringIO
import eulogger
import hashlib
import types
import operator
import fcntl
import struct
import subprocess
import termios
from functools import wraps


class TimeoutFunctionException(Exception): 
    """Exception to raise on a timeout""" 
    pass


class Eutester(object):

    # Force ansi escape sequences (markup) in output.
    # This can also be set as an env var
    _EUTESTER_FORCE_ANSI_ESCAPE = False
    # Allow ansi color codes outside the standard range. For example some systems support
    # a high intensity color range from 90-109.
    # This can also be set as an env var
    _EUTESTER_NON_STANDARD_ANSI_SUPPORT = False

    def __init__(self, credpath=None):
        """This class is intended to setup boto connections for the various services that the *ops classes will use.
        :param credpath: Path to a valid eucarc file.
        :param aws_access_key_id: Used in conjuction with aws_secret_access_key allows for creation of connections without needing a credpath.
        :param aws_secret_access_key: Used in conjuction with aws_access_key_id allows for creation of connections without needing a credpath.
        :rtype: :class:`eutester.Eutester` or ``None``
        :returns: A Eutester object with all connections that were able to be created. Currently EC2, S3, IAM, and STS.
        """

        ### Default values for configuration
        self.credpath = credpath
        
        ### Eutester logs
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
            self.account_id = self.get_account_id()
            self.user_id = self.get_user_id()

    @property
    def ec2_certpath(self):
        try:
            return  self.parse_eucarc('EC2_CERT')
        except ValueError:
             return None

    @property
    def ec2_cert(self):
        certpath = self.ec2_certpath
        if certpath and os.path.exists(certpath):
            out = self.local('cat {0}'.format(certpath))
            return str("\n".join(out)).strip()
        return None

    @property
    def ec2_private_key_path(self):
        try:
            return self.parse_eucarc('EC2_PRIVATE_KEY')
        except ValueError:
            return None

    @property
    def ec2_private_key(self):
        keypath = self.ec2_private_key_path
        if keypath and os.path.exists(keypath):
            out = self.local('cat {0}'.format(keypath))
            return "\n".join(out)
        return None

    def get_access_key(self):
        if not self.aws_access_key_id:     
            """Parse the eucarc for the EC2_ACCESS_KEY"""
            self.aws_access_key_id = self.parse_eucarc("EC2_ACCESS_KEY")  
        return self.aws_access_key_id 
    
    def get_secret_key(self):
        if not self.aws_secret_access_key: 
            """Parse the eucarc for the EC2_SECRET_KEY"""
            self.aws_secret_access_key = self.parse_eucarc("EC2_SECRET_KEY")
        return self.aws_secret_access_key
    
    def get_account_id(self):
        if not self.account_id:
            """Parse the eucarc for the EC2_ACCOUNT_NUMBER"""
            self.account_id = self.parse_eucarc("EC2_ACCOUNT_NUMBER")
        return self.account_id
    
    def get_user_id(self):
        if not self.user_id:
            self.user_id = self.parse_eucarc("EC2_USER_ID")
        """Parse the eucarc for the EC2_ACCOUNT_NUMBER"""
        return self.user_id

    def get_port(self):
        """Parse the eucarc for the EC2_ACCOUNT_NUMBER"""
        ec2_url = self.parse_eucarc("EC2_URL")
        return ec2_url.split(':')[1].split("/")[0]

    def parse_eucarc(self, field):
        if self.credpath is None:
            raise RuntimeError('Credpath has not been set yet. '
                               'Please set credpath or provide '
                               'configuration file')
        cmd = 'bash -c \'source {0}/eucarc &> /dev/null && echo ${1}\''.format(self.credpath, field)
        out = self.local(cmd)
        if out[0]:
            return out[0]
        else:
            if out:
                out = "\n".join(out)
            self.critical('Failed to find field: {0},\nCommand:{1}\nReturned:\n"{2}"'
                          .format(field, cmd, out))
            try:
                catcmd = 'cat {0}/eucarc | grep {1}'.format(self.credpath, field)
                catout = self.local(catcmd)
                catout = "\n".join(catout)
            except Exception, ce:
                catout = "Command failed:{0}, err:{1}".format(catcmd, ce)
            self.critical("Unable to find {0} id in eucarc. {1}:\n{2}\n"
                          .format(field, catcmd, catout))
            raise ValueError("Unable to find " +  field + " id in eucarc")

    def handle_timeout(self, signum, frame): 
        raise TimeoutFunctionException()

    def local(self, cmd, shell=True):
        """
        Run a command on the localhost
        :param cmd: str representing the command to be run
        :return: :raise: CalledProcessError on non-zero return code
        """
        args = cmd
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   bufsize=4096, shell=shell)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            self.debug('CMD:"{0}"\nOUTPUT:\n{1}'.format(cmd, str(output)))
            error = subprocess.CalledProcessError(retcode, cmd)
            error.output = output
            raise error
        return output.split("\n")

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
        for x in xrange(0, poll_count):
            try:
                self.local("ping -c 1 " + address)
                self.debug("Was able to ping address")
                return True
            except subprocess.CalledProcessError as CPE:
                self.debug('Output:' + str(CPE.output))
                self.debug('Ping attempt {0}/{1} failed, err:{2}'
                           .format(x, poll_count, str(CPE)))
                self.sleep(2)
        self.critical("Was unable to ping address")
        return False

    @classmethod
    def markup(cls, text, markups=[1], resetvalue="\033[0m", force=None, allow_nonstandard=None):
        """
        Convenience method for using ansi markup. Attempts to check if terminal supports
        ansi escape sequences for text markups. If so will return a marked up version of the
        text supplied using the markups provided.
        Some example markeups: 1 = bold, 4 = underline, 94 = blue or markups=[1, 4, 94]
        :param text: string/buffer to be marked up
        :param markups: a value or list of values representing ansi codes.
        :param resetvalue: string used to reset the terminal, default: "\33[0m"
        :param force: boolean, if set will add escape sequences regardless of tty. Defaults to the
                      class attr '_EUTESTER_FORCE_ANSI_ESCAPE' or the env variable:
                      'EUTESTER_FORCE_ANSI_ESCAPE' if it is set.
        :param allow_nonstandard: boolean, if True all markup values will be used. If false
                                  the method will attempt to remap the markup value to a
                                  standard ansi value to support tools such as Jenkins, etc.
                                  Defaults to the class attr '._EUTESTER_NON_STANDARD_ANSI_SUPPORT'
                                  or the environment variable 'EUTESTER_NON_STANDARD_ANSI_SUPPORT'
                                  if set.
        returns a string with the provided 'text' formatted within ansi escape sequences
        """
        if not isinstance(markups, list):
            markups = [markups]
        if force is None:
            force = os.environ.get('EUTESTER_FORCE_ANSI_ESCAPE', cls._EUTESTER_FORCE_ANSI_ESCAPE)
            if str(force).upper() == 'TRUE':
                force = True
            else:
                force = False
        if allow_nonstandard is None:
            allow_nonstandard = os.environ.get('EUTESTER_NON_STANDARD_ANSI_SUPPORT',
                                               cls._EUTESTER_NON_STANDARD_ANSI_SUPPORT)
            if str(allow_nonstandard).upper() == 'TRUE':
                allow_nonstandard = True
            else:
                allow_nonstandard = False
        if not force:
            if not (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()):
                return text
        if not allow_nonstandard:
            newmarkups = []
            for markup in markups:
                if markup > 90:
                    newmarkups.append(markup-60)
                else:
                    newmarkups.append(markup)
            markups = newmarkups
        lines = []
        markupvalues=";".join(str(x) for x in markups)
        for line in text.splitlines():
            lines.append("\033[{0}m{1}\033[0m".format(markupvalues, line))
        buf = "\n".join(lines)
        if text.endswith('\n') and not buf.endswith('\n'):
            buf += '\n'
        return buf

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
    
    def test_port_status(self,
                         ip,
                         port,
                         timeout=5,
                         tcp=True,
                         recv_size=0,
                         send_buf=None,
                         verbose=True):
        '''
        Attempts to connect to tcp port at ip:port within timeout seconds
        '''
        ret_buf = ""
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
                #for UDP always try send
                if send_buf is None:
                    send_buf = "--TEST LINE--"
            if send_buf is not None:
                s.sendto(send_buf, (ip, port))
            if recv_size:
                ret_buf = s.recv(recv_size)
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
        return ret_buf

    def grep(self, string,list):
        """ Remove the strings from the list that do not match the regex string"""
        expr = re.compile(string)
        return filter(expr.search,list)

    def diff(self, list1, list2):
        """Return the diff of the two lists"""
        return list(set(list1)-set(list2))
    
    def fail(self, message):
        self.critical(message)
        #self.fail_log.append(message)
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

    @staticmethod
    def render_file_template(src, dest, **kwargs):
        import jinja2
        with open(src) as sfile:
            templ = jinja2.Template(sfile.read())
            with open(dest, 'w') as dfile:
                dfile.write(templ.render(kwargs))
    
    def id_generator(self, size=6, chars=string.ascii_uppercase + string.ascii_lowercase  + string.digits ):
        """Returns a string of size with random charachters from the chars array.
             size    Size of string to return
             chars   Array of characters to use in generation of the string
        """
        return ''.join(random.choice(chars) for x in range(size))

    @staticmethod
    def get_terminal_size():
        '''
        Attempts to get terminal size. Currently only Linux.
        returns (height, width)
        '''
        h=30
        w=80
        try:
            # todo Add Windows support
            t_h,t_w = struct.unpack('hh', fcntl.ioctl(sys.stdout,
                                                   termios.TIOCGWINSZ,
                                                   '1234'))
            #Temp hack. Some env will return <= 1
            if t_h > 1 and t_w > 1:
                h = t_h
                w = t_w
        except:
            pass
        return (h,w)

    @staticmethod
    def get_line(length=None):
        line = ""
        if not length:
            try:
                length = Eutester.get_terminal_size()[1]
                if length <= 1:
                    length = 80
            except:
                length = 80
        for x in xrange(0,int(length)):
            line += "-"
            return "\n" + line + "\n"



    @classmethod
    def printinfo(cls, func):
        '''
        Decorator to print method positional and keyword args when decorated method is called
        usage:
        @printinfo
        def myfunction(self, arg1, arg2, kwarg1=defaultval):
            stuff = dostuff(arg1, arg2, kwarg1)
            return stuff
        When the method is run it will produce debug output showing info as to how the method was called, example:
        
        myfunction(arg1=123, arg2='abc', kwarg='words)
        
        2013-02-07 14:46:58,928] [DEBUG]:(mydir/myfile.py:1234) - Starting method: myfunction()
        2013-02-07 14:46:58,928] [DEBUG]:---> myfunction(self, arg1=123, arg2=abc, kwarg='words')
        '''

        @wraps(func)
        def methdecor(*func_args, **func_kwargs):
            _args_dict = {} # If method has this kwarg populate with args here
            try:
                defaults = func.func_defaults
                kw_count = len(defaults or [])
                selfobj = None
                arg_count = func.func_code.co_argcount - kw_count
                var_names = func.func_code.co_varnames[:func.func_code.co_argcount]
                arg_names = var_names[:arg_count]
                kw_names =  var_names[arg_count:func.func_code.co_argcount]
                kw_defaults = {}
                for kw_name in kw_names: 
                    kw_defaults[kw_name] = defaults[kw_names.index(kw_name)]
                arg_string=''
                # If the underlying method is using a special kwarg named
                # '_args_dict' then provide all the args & kwargs it was
                # called with in that dict for inspection with that method
                if 'self' in var_names and len(func_args) <= 1:
                    func_args_empty = True
                else:
                    func_args_empty = False
                if (not func_args_empty or func_kwargs) and \
                                '_args_dict' in kw_names:
                    if not '_args_dict' in func_kwargs or \
                            not func_kwargs['_args_dict']:
                        func_kwargs['_args_dict'] = {'args':func_args,
                                                     'kwargs':func_kwargs}
                #iterate on func_args instead of arg_names to make sure we pull out self object if present
                for count, arg in enumerate(func_args):
                    if count == 0 and var_names[0] == 'self': #and if hasattr(arg, func.func_name):
                        #self was passed don't print obj addr, and save obj for later
                        arg_string += 'self'
                        selfobj = arg
                    elif count >= arg_count:
                        #Handle case where kw args are passed w/o key word as a positional arg add 
                        #Add it to the kw_defaults so it gets printed later
                        kw_defaults[var_names[count]] = arg
                    else:
                        #This is a positional arg so grab name from arg_names list
                        arg_string += ', '
                        arg_string += str(arg_names[count])+'='+str(arg)
                kw_string = ""
                for kw in kw_names:
                    kw_string += ', '+str(kw)+'='
                    if kw in func_kwargs:
                        kw_string += str(func_kwargs[kw])
                    else:
                        kw_string += str(kw_defaults[kw])
                debugstring = '\n--->('+str(os.path.basename(func.func_code.co_filename))+":"+str(func.func_code.co_firstlineno)+")Starting method: "+str(func.func_name)+'('+arg_string+kw_string+')'
                debugmethod = None
                if selfobj and hasattr(selfobj,'debug'):
                    debug = getattr(selfobj, 'debug')
                    if isinstance(debug, types.MethodType):
                        debugmethod = debug
                if debugmethod:    
                    debugmethod(debugstring)
                else:
                    print debugstring
            except Exception, e:
                print Eutester.get_traceback()
                print 'printinfo method decorator error:'+str(e)
            return func(*func_args, **func_kwargs)
        return methdecor

    def wait_for_result(self,
                        callback,
                        result,
                        timeout=60,
                        poll_wait=10,
                        oper=operator.eq,
                        allowed_exception_types=None,
                        **callback_kwargs):
        """
        Wait for the instance to enter the state

        :param instance: Boto instance object to check the state on
        :param result: result from the call back provided that we are looking for
        :param poll_count: Number of 10 second poll intervals to wait before failure (for legacy test script support)
        :param timeout: Time in seconds to wait before failure
        :param oper: operator obj used to evaluate 'result' against callback's result. ie operator.eq, operator.ne, etc..
        :return: result upon success
        :raise: Exception when instance does not enter proper state
        """
        allowed_exception_types = allowed_exception_types or []
        self.debug( "Beginning poll loop for result " + str(callback.func_name) + " to go to " + str(result) )
        start = time.time()
        elapsed = 0
        current_state =  callback(**callback_kwargs)
        ### If the instance changes state or goes to the desired state before my poll count is complete
        while( elapsed <  timeout and not oper(current_state,result) ):
            self.debug(  str(callback.func_name) + ' returned: "' + str(current_state) + '" after '
                       + str(elapsed/60) + " minutes " + str(elapsed%60) + " seconds.")
            self.sleep(poll_wait)
            try:
                current_state = callback(**callback_kwargs)
            except allowed_exception_types as AE:
                self.debug('Caught allowed exception:' + str(AE))
                pass
            elapsed = int(time.time()- start)
        self.debug(  str(callback.func_name) + ' returned: "' + str(current_state) + '" after '
                    + str(elapsed/60) + " minutes " + str(elapsed%60) + " seconds.")
        if not oper(current_state,result):
            raise WaitForResultException( str(callback.func_name) + " did not return " + str(operator.ne.__name__) +
                             "(" + str(result) + ") true after elapsed:"+str(elapsed))
        return current_state

    def get_md5_for_file(self, filepath, machine=None):
        if machine:
            machinename = machine.hostname
            out = machine.sys('md5sum {0}'.format(filepath), code=0)
            md5string = str(out[0]).split()[0]
        else:
            machinename = 'local'
            # If a machine wasn't provided try local...
            md5 = hashlib.md5()
            length = md5.block_size * 128
            with open(filepath, "rb") as f:
                while True:
                    buf = f.read(length)
                    if not buf:
                        break
                    md5.update(buf)
            md5string = str(md5.hexdigest())
        self.debug('MD5 for {0} on {1} is: "{2}"'.format(filepath, machinename, md5string))
        return md5string

    @classmethod
    def get_traceback(cls):
        '''
        Returns a string buffer with traceback, to be used for debug/info purposes. 
        '''
        try:
            out = StringIO.StringIO()
            traceback.print_exception(*sys.exc_info(),file=out)
            out.seek(0)
            buf = out.read()
        except Exception, e:
                buf = "Could not get traceback"+str(e)
        return str(buf) 
    
    def __str__(self):
        return 'got self'



class WaitForResultException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


