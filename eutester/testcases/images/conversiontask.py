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
from boto.ec2.ec2object import TaggedEC2Object, EC2Object
from boto.ec2.connection import EC2ResponseError


class ConversionTask(TaggedEC2Object):
    _IMPORTINSTANCE = 'importinstance'
    _IMPORTVOLUME  = 'importvolume'

    def __init__(self, connection=None):
        super(ConversionTask, self).__init__(connection)
        self.connection = connection
        self.conversiontaskid = None
        self.expirationtime = None
        self.state = None
        self.statusmessage = None
        self._importinstancetask = None
        self._importvolumetask = None
        self._instance = None
        self._snapshots = None
        self.tags = None
        self.notfound = False

    def __repr__(self):
        volumes = ",".join([vol.id for vol in self.volumes])
        return ('ConversionTask:"{0}", state:"{1}", instance:"{2}", '
                'volumes:"{3}", status:"{4}"'
                .format(str(self.conversiontaskid),
                        self.state,
                        self.instanceid,
                           volumes,
                        self.statusmessage))

    @property
    def availabilityzone(self):
        if self.importvolumes:
            return self.importvolumes[0].availabilityzone
        return None

    @property
    def importvolumes(self):
        if self._importinstancetask:
            return self._importinstancetask.importvolumes
        if self._importvolumetask:
            return [self._importvolumetask]
        return []

    @property
    def platform(self):
        if self._importinstancetask:
            return self._importinstancetask.platform
        return None

    @property
    def instanceid(self):
        if self._importinstancetask:
            return self._importinstancetask.instanceid
        return None

    @property
    def instance(self):
        if not self._instance and self.instanceid:
            ins = self._instance = self.connection.get_only_instances(
                instance_ids=[self.instanceid])
            if ins:
                self._instance = ins[0]
        return self._instance

    @property
    def volumes(self):
        '''
        Volumes are updated during the task and there may not be a volume(s)
        associated with a task response right away, EUCA-9337
        '''
        ret = []
        for im in self.importvolumes:
            if im and im.volume:
                ret.append(im.volume)
        return ret

    @property
    def snapshots(self):
        if not self._snapshots:
            self._snapshots = []
            for volume in self.volumes:
                self._snapshots.extend(self.connection.get_all_snapshots(
                    filters={'volume-id':volume.id}))
        return self._snapshots

    @property
    def image_id(self):
        if self.instance:
            return self.instance.image_id

    @property
    def tasktype(self):
        if self._importinstancetask:
            return self._IMPORTINSTANCE
        elif self._importvolumetask:
            return self._IMPORTVOLUME
        else:
            return None

    @property
    def id(self):
        return self.conversiontaskid

    @id.setter
    def id(self, taskid):
        self.conversiontaskid = taskid

    def cancel(self):
        params = {'ConversionTaskId':str(self.conversiontaskid)}
        task = self.connection.get_object('CancelConversionTask',
                                          params,
                                          ConversionTask,
                                          verb='POST')
        if task:
            self.update(updatedtask=task)
        return task

    def update(self, updatedtask=None):
        params = {}
        params['ConversionTaskId'] = str(self.conversiontaskid)
        if not updatedtask:
            updatedtask = self.connection.get_object('DescribeConversionTasks',
                                                     params,
                                                     ConversionTask,
                                                     verb='POST')
        if updatedtask:
            self.__dict__.update(updatedtask.__dict__)
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
            self._importvolumetask = ImportVolume(connection=connection)
            self.importvolumes.append(self._importvolumetask)
            return self._importvolumetask
        elif ename == 'importInstance':
            self._importinstancetask = ImportInstance(connection=connection)
            return self._importinstancetask
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



class ImportVolume(EC2Object):
    def __init__(self, connection=None):
        super(ImportVolume, self).__init__(connection)
        self.bytesconverted = None
        self.availabilityzone = None
        self.image = None
        self.volumes = self
        self._importvolume = None

    @property
    def volume_id(self):
        if self._importvolume:
            return self._importvolume.id
        else:
            return None

    @property
    def volume_size(self):
        if self._importvolume:
            return self._importvolume.size
        else:
            return None

    @property
    def volume(self):
        if self._importvolume:
            return self._importvolume.volume
        else:
            return None

    @volume.setter
    def volume(self, newvol):
        if self._importvolume:
            if newvol.id == self._importvolume.id:
                self._importvolume.volume = newvol
            else:
                raise ValueError('Can not set volume with different '
                                 'id than original')

    def startElement(self, name, attrs, connection):
        elem = super(ImportVolume, self).startElement(name,
                                                      attrs,
                                                      connection)
        self.connection = connection
        if elem is not None:
            return elem
        ename = name.lower().replace('euca:','')
        if ename == 'image':
            self.image = ConversionTaskImage(connection=connection)
            return self.image
        elif ename == 'volume':
            self._importvolume = ConversionTaskVolume(connection=connection)
            return self._importvolume
        else:
            return None

    def endElement(self, name, value, connection):
        ename = name.lower().replace('euca:','')
        if ename == 'bytesconverted':
            self.bytesconverted = value
        elif ename == 'availabilityzone':
            self.availabilityzone = value
        elif ename != 'importvolume':
            setattr(self, ename, value)


class ImportInstance(EC2Object):
    def __init__(self, connection=None):
        super(ImportInstance, self).__init__(connection)
        self.bytesconverted = None
        self.image = None
        self.platform = None
        self.instanceid = None
        self.importvolumes = []

    def startElement(self, name, attrs, connection):
        elem = super(ImportInstance, self).startElement(name,
                                                            attrs,
                                                            connection)
        if elem is not None:
            return elem
        ename = name.lower().replace('euca:','')
        if ename == 'image':
            self.image = ConversionTaskImage(connection=connection)
            return self.image
        elif ename == 'volumes':
            self.importvolumes = ResultSet([('item', ImportVolume),
                                            ('euca:item', ImportVolume)])
            return self.importvolumes
        else:
            return None

    def endElement(self, name, value, connection):
        ename = name.lower().replace('euca:','')
        if ename == 'bytesconverted':
            self.bytesconverted = value
        elif ename == 'availabilityzone':
            self.availabilityzone = value
        elif ename == 'platform':
            self.platform = value
        elif ename == 'instanceid':
            self.instanceid = value
        elif ename != 'importinstance':
            setattr(self, ename, value)

class ConversionTaskImage(object):
    def __init__(self, connection=None):
        self.connection = connection
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

class ConversionTaskVolume(EC2Object):
    def __init__(self, connection=None):
        super(ConversionTaskVolume, self).__init__(connection)
        self.id = None
        self.size = None
        self._volume = None

    def __repr__(self):
        return 'ConversionTaskVolume:' + str(self.id)

    @property
    def volume(self):
        if self.connection and not self._volume:
            if (self.id):
                try:
                    volumes = self.connection.get_all_volumes([self.id])
                    for volume in volumes:
                        if volume.id == self.id:
                            self.volume = volume
                            break
                except EC2ResponseError as EE:
                    print sys.stderr, 'Failed to fetch volume:' + \
                                      str(self.id) + ' for ' \
                                      'import task:' + str(EE)
        return self._volume

    @volume.setter
    def volume(self, newvol):
        self._volume = newvol

    def startElement(self, name, attrs, connection):
        elem = super(ConversionTaskVolume, self).startElement(name,
                                                              attrs,
                                                              connection)
        if elem is not None:
            return elem
        pass

    def endElement(self, name, value, connection):
        ename = name.lower().replace('euca:','')
        if ename == 'id':
            self.id = value
        elif ename == 'size':
            self.size = value
        elif ename != 'volume':
            setattr(self, ename, value)
