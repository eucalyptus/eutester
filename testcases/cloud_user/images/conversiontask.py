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
# Author: matt.clark@eucalyptus.com

import sys


class ConversionTask(object):
    def __init__(self, connection=None):
        self.connection = connection
        self.conversiontaskid = None
        self.notfound = False

    def __repr__(self):
        return 'ConversionTask:' + str(self.conversiontaskid)

    def update(self):
        params = {}
        params['ConversionTaskId'] = str(self.conversiontaskid)
        task = self.connection.get_object('DescribeConversionTasks',
                                          params,
                                          ConversionTask,
                                          verb='POST')
        if task:
            self.__dict__.update(task.__dict__)
        else:
            print sys.stderr, 'Update. Failed to find task:"{0}"'\
                .format(str(self.conversiontaskid))
            self.notfound = True

    def startElement(self, name, attrs, connection):
        pass

    def endElement(self, name, value, connection):
        ename = name.lower().replace('euca:','')
        if ename == 'conversiontaskid':
            self.conversiontaskid = value
        else:
            setattr(self, ename, value)

