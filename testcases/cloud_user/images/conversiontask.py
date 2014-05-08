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
from boto.resultset import ResultSet
from boto.ec2.tag import Tag
from boto.ec2.ec2object import TaggedEC2Object
from boto.ec2.connection import EC2ResponseError


class ConversionTask(TaggedEC2Object):
    def __init__(self, connection=None):
        super(ConversionTask, self).__init__(connection)
        self.connection = connection
        self.conversiontaskid = None
        self.expirationtime = None
        self.importvolumetask = None
        self.volume = None
        self._volume = None
        self.state = None
        self.statusmessage = None
        self.tags = None
        self.notfound = False

    def __repr__(self):
        return ('ConversionTask:"{0}", state:"{1}", volume:"{2}", status:"{3}"'
                .format(str(self.conversiontaskid),
                        self.state,
                        self.volume,
                        self.statusmessage))

    @property
    def id(self):
        return self.conversiontaskid

    @id.setter
    def id(self, taskid):
        self.conversiontaskid = taskid

    @property
    def volume(self):
        if self.connection and not self._volume:
            if (self.importvolumetask and
                    hasattr(self.importvolumetask,'volume_id') and
                    self.importvolumetask.volume_id):
                try:
                    volumes = self.connection.get_all_volumes(
                        [self.importvolumetask.volume_id])
                    for volume in volumes:
                        if volume.id == self.importvolumetask.volume_id:
                            self.volume = volume
                            break
                except EC2ResponseError as EE:
                    print sys.stderr, 'Failed to fetch volume for ' \
                                      'import task:' + str(EE)
        return self._volume

    @volume.setter
    def volume(self, newvol):
        self._volume = newvol

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
        ename = name.replace('euca:','')
        elem = super(ConversionTask, self).startElement(name,
                                                        attrs,
                                                        connection)
        if elem is not None:
            return elem
        if ename == 'importVolume':
            self.importvolumetask = ImportVolumeTask()
            print self.importvolumetask
            if (self.importvolumetask and
                    hasattr(self.importvolumetask,'volume_id') and
                    self.importvolumetask.volume_id):
                try:
                    self.volume = connection.get_all_volumes(
                        [self.importvolumetask.volume_id])
                except EC2ResponseError as EE:
                    print sys.stderr, 'Failed to fetch volume for ' \
                                      'import task:' + str(EE)
            return self.importvolumetask
        elif ename == 'tagSet' or ename == 'resourceTagSet':
            self.tags = ResultSet([('item', Tag)])
            return self.tags
        else:
            return None

    def endElement(self, name, value, connection):
        ename = name.lower().replace('euca:','')
        if ename == 'conversiontaskid':
            self.conversiontaskid = value
        elif ename == 'expirationtime':
            self.expirationtime = value
        elif ename == 'state':
            self.state = value
        elif ename == 'statusmessage':
            self.statusmessage = value
        else:
            setattr(self, ename, value)


class ImportVolumeTask(object):
    def __init__(self, connection=None):
        self.connection = connection
        self.bytesconverted = None
        self.availabilityzone = None
        self.image = None
        self._volume_info = ConversionTaskVolume()

    @property
    def volume_id(self):
        return self._volume_info.id

    @property
    def volume_size(self):
        return self._volume_info.size

    def startElement(self, name, value, connection):
        ename = name.lower().replace('euca:','')
        if ename == 'image':
            self.image = ConversionTaskImage()
            return self.image
        elif ename == 'volume':
            return self._volume_info
        else:
            return None

    def endElement(self, name, value, connection):
        ename = name.lower().replace('euca:','')
        if ename == 'bytesconverted':
            self.bytesconverted = value
        elif ename == 'availabilityzone':
            self.availabilityzone = value
        elif ename != self.__class__.__name__.lower():
            setattr(self, ename, value)


class ConversionTaskImage(object):
    def __init__(self):
        self.format = None
        self.importmanifesturl = None
        self.size = None

    def __repr__(self):
        return 'ConversionTaskImage:' + str(self.importmanifesturl)

    def startElement(self, name, value, connection):
        pass

    def endElement(self, name, value, connection):
        ename = name.lower().replace('euca:','')
        if ename == 'format':
            self.format = value
        elif ename == 'size':
            self.size = value
        elif ename == 'importmanifesturl':
            self.importmanifesturl = value
        elif ename != 'image':
            setattr(self, ename, value)

class ConversionTaskVolume(object):
    def __init__(self, connection=None):
        self.id = None
        self.size = None

    def __repr__(self):
        return 'ConversionTaskVolume:' + str(self.id)

    def startElement(self, name, value, connection):
        pass

    def endElement(self, name, value, connection):
        ename = name.lower().replace('euca:','')
        if ename == 'id':
            self.id = value
        elif ename == 'size':
            self.size = value
        elif ename != 'volume':
            setattr(self, ename, value)
