'''
Tar Utilities 
''' 
import os
import re
import sys
import time
import commands
import tarfile
import urllib2
import cStringIO
import errno
    
class Tarutils():
    '''
    Basic tar utilities interface to be extended
    '''
    def __init__(self,uri, headersize=512, printmethod=None, fileformat=None, verbose=True):
        self.uri = uri
        self.headersize=headersize
        self.verbose = verbose
        self.printmethod = printmethod
        self.fileformat = fileformat
        self.members = None
        self.filesize = None
        self.update()
        
        
    def debug(self, msg, verbose=None):
        msg = str(msg)
        verbose = verbose or self.verbose
        if verbose:
            if self.printmethod:
                self.printmethod(msg)
            else:
                print(msg)
        
    def update(self):
        self.get_fileformat()
        self.filesize = self.get_file_size(self.uri)
        self.members = self.get_members(self.uri, headersize=self.headersize)
    
    def get_fileformat(self):
        if re.search('.gz$',self.uri):
            self.fileformat = 'r:gz'
        else:
            self.fileformat = 'r'
    
    def get_members(self, uri=None, headersize=None):
        raise NotImplementedError( "Mandatory tar method not implemented" )
    
    def get_member(self, name):
        raise NotImplementedError( "Mandatory tar method not implemented" )
    
    def extract_member(self, memberpath,destpath=''):
        raise NotImplementedError( "Mandatory tar method not implemented" )
    
    def extract_all(self, destpath=''):
        raise NotImplementedError( "Mandatory tar method not implemented" )
    
    def get_file_offset(self, uri=None, start=0, offset=None, filesize=None):
        raise NotImplementedError( "Mandatory tar method not implemented" )  
    
    def get_file_size(self,ur=None):
        raise NotImplementedError( "Mandatory tar method not implemented" )
    
    def show_members(self):
        for member in self.members:
            self.debug(member.name,verbose=True)
    
    def get_freespace(self,path='.'):
        while not os.path.exists(path) and len(path):
            basename = os.path.basename(path)
            if basename:
                path = path.replace(basename,'')
            path = path.rstrip('/')
        st = os.statvfs(path)
        return (st.f_bsize * st.f_bavail)
    
    def make_path(self,filepath):
        '''
        Make sure the directories/path to our file exists, if not make it
        '''
        self.debug('filepath:'+str(filepath))
        path = os.path.dirname(filepath)
        if path:
            try:
                os.makedirs(path)
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise
        return str(path)+'/'+str(os.path.basename(filepath))
    
    def list(self):
        for member in self.members:
            output=""
            output= tarfile.filemode(member.mode)
            output= output +( " %s/%s " % (member.uname or member.uid, member.gname or member.gid))
            if member.ischr() or member.isblk():
                output = output+( "%10s " % ("%d,%d" % (member.devmajor, member.devminor)) )
            else:
                output = output+ "%10d" % member.size
            output = output + " %d-%02d-%02d %02d:%02d:%02d " % time.localtime(member.mtime)[:6]

            output = output + member.name + ("/" if member.isdir() else "")

            if member.issym():
                output=output + "->", member.linkname,
            if member.islnk():
                output = output + "link to", member.linkname,
            self.debug(output)
    
    def close(self):
        raise NotImplementedError( "Mandatory tar method not implemented" )
        
    
class Local_Tarutils(Tarutils):
    '''
    Tar utilties for local files
    '''
    
    def __init__(self, uri, headersize=512, printmethod=None, verbose=True):
        self.tarfile = None
        tarutil.__init__(self, uri, headersize=512, printmethod=None, verbose=True)
        
        
    def update(self):
        self.uri = str(self.uri).replace('file://', '')
        #reset file in case it has changed since last update
        self.close()
        self.tarfile = tarfile.open(name=self.uri, mode = self.fileformat)
        tarutil.update(self)
    
    
    def get_members(self, uri=None, headersize=None):
        return self.tarfile.getmembers()
    
    def get_member(self, membername):
        return self.tarfile.getmember(membername)
    
    def extract_member(self, memberpath, destpath='.'):
        member = self.get_member(memberpath)
        freespace = self.get_freespace(destpath)
        if member.size > freespace:
            raise Exception(str(memberpath)+":"+str(member.size)+" exceeds destpath freespace:"+(destpath)+":"+str(freespace) )
        return self.tarfile.extract(member, path=destpath)
    
    def extract_all(self, list=None, destpath='.'):
        list = list or self.members
        size = 0
        for member in list:
            size += int(member.size)
        freespace = self.get_freespace(destpath)
        if size > freespace:
            raise Exception("Extract_all size:"+str(size)+" exceeds destpath freespace:"+(destpath)+":"+str(freespace) )
        return self.tarfile.extractall(members=list)
    
    def get_file_size(self,ur=None):
        return os.path.getsize(self.uri)
    
    def close(self):
        if self.tarfile and not self.tarfile.closed:
            self.tarfile.close()
    
    

class Http_Tarutils(Tarutils):
    '''
    Utility class for navigating and operating on remote tarfiles via http
    '''
    def get_members(self, url = None, headersize=None, mode=None):
        '''
        Attempts to step through all tarball headers and gather the members/file info contained within.
        Will update self.members with the returned list of members.
        url - optional - remote http address of tarball
        headersize - optional - tar header size to be used
        mode - optional - the file format string used for read the file (ie gzip'd or not)
        returns a list of Tarinfo member objects
        '''
        headersize = headersize or self.headersize
        mode = mode or self.fileformat
        url = url or self.uri
        filesize = self.filesize or self.get_file_size(url)
        start = 0
        headers=[]
        end = 0 
        self.debug("get_members for url:"+str(url)+", headersize:"+str(headersize)+", filesize:"+str(filesize))
        while (start+headersize) <= filesize and end < 2:
            data = self.download_http_offset(url, start=start, offset=headersize)
            if not len(data.getvalue().replace('\x00','')):
                #End of Tar markers are 2 consecutive zero filled 512byte buffers
                self.debug('Got empty header, count:'+str(end))
                end += 1
                start += headersize
            else:
                end = 0
                #print 'got data:'+str(data.read())
                data.seek(0)
                #get tar member info from this header
                member = tarfile.TarInfo.frombuf(data.getvalue())
                member.offset = start
                member.offset_data = start + headersize
                #append tar header/member to the list
                self.debug("Got header:"+member.name)
                headers.append(member)
                #move start point forward by the size of the file and header info. 
                start = headersize + member.size
            #must end in an increment of headersize 512 ...or maybe tarfile.fileobject.blocksize ie:1024? 
            if start%headersize != 0:
                start = ((start/headersize)+1)*headersize
        self.members = headers
        return headers
            
    def get_member(self, memberpath):
        '''
        Traverses our self.members list and attempts to return a tarinfo member object 
        which member.name matches the provided memberpath
        '''
        members = self.members or self.get_members()
        for member in members:
            if member.name == memberpath:
                return member
        return None
    
    def extract_member(self,memberpath, uri=None, filesize=None, readsize=None, destpath='.'):
        '''
        Extracts a tarball member to a file at destpath/<member name>
        if destpath is None, will write to a stringIO object in memory instead. 
        member - mandatory - string, relative path with tarball of file/member to extract
        uri - optional - remote url of the tarball
        filesize - optional - size of remote tarball 
        readsize - optional - size to read/write per iteration 
        destpath - destination dir/path to download the member data to
        '''
        uri = uri or self.uri
        member = self.get_member(memberpath)
        fileobj = self.extract_member_obj(member, uri=uri, filesize=filesize, destpath=destpath)
        if not fileobj.closed:
            fileobj.close()
        
     
    def extract_member_obj(self, member, uri=None, filesize=None, readsize=None, destpath='.'):
        '''
        Extracts a tarball member to a file at destpath/<member name>
        if destpath is None, will write to a stringIO object in memory instead. 
        Returns the file or file like object 
        member - mandatory - tarfile.TarInfo member object 
        uri - optional - remote url of the tarball
        filesize - optional - size of remote tarball 
        readsize - optional - size to read/write per iteration 
        destpath - destination dir/path to download the member data to
        '''
        self.debug('Attempting to extract member: '+str(member.name)+' to dir: '+str(destpath))
        uri = uri or self.uri
        filesize = filesize or self.filesize
        freespace = self.get_freespace(destpath)
        if member.size > freespace:
            raise Exception(str(memberpath)+":"+str(member.size)+" exceeds destpath freespace:"+(destpath)+":"+str(freespace) )
        start = member.offset_data
        offset = member.size
        destfile=str(destpath).rstrip('/')+'/'+str(member.name)
        file = self.get_file_offset(uri, start, offset, filesize, readsize=None,destfile=destfile)
        self.debug('Extracted member: '+str(member.name)+' to file: '+str(file.name))
        return file
    
    def extract_all(self, memberlist=None,destpath=''):
        '''
        Attempts to extract all members from list to local destination at 'destpath'
        Attempts to guesstimate the the size needed and check available space at destpath before extracting
        memberlist - optional - list of tarinfo member objects
        destpath - optional - local destination to download/extract to
        '''
        list = memberlist or self.members
        size = 0
        for member in list:
            size += int(member.size)
        freespace = self.get_freespace(destpath)
        if size > freespace:
            raise Exception("Extract_all size:"+str(size)+" exceeds destpath freespace:"+(destpath)+":"+str(freespace) )
        for member in self.members:
            file = self.extract_member_obj(member, destpath=destpath)
            if not file.closed:
                file.close()
        
        
    def get_file_offset(self, uri=None, start=0, offset=None, filesize=None, readsize=None,destfile=None):
        '''
        mapped method to down_load_http_offset
        '''
        return self.download_http_offset(uri, start=start, offset=offset, filesize=filesize, destfile=destfile)
    
    
    def download_http_offset(self, url=None, start=0, offset=None, filesize=None, readsize=None, destfile=None):
        '''
        Get data from range start to offset, return it in a cString file like object. 
        Returns either an actual file object if a destfile is specified, or returns a string buffer 'file like' cStringIO object
        url:    url to read from 
        start:  start address to read from
        offset: length in bytes to read from starting address
        filesize: the size of the remote file we're reading. Can be given to avoid querrying the remote file over and over
        readsize: the incremental read size used when reading from http and writing to our file or buffer
        destfile: the local file to write to, if not specified method will store/write to string buffer      
        '''
        url = url or self.uri
        readsize = readsize or (16 * 1024)
        filesize = self.filesize or int(self.get_file_size(url))
        dfile = None #potential destination file desc. to write downloaded data to
        retbuf = "" #potential buffer to hold downloaded data
        self.debug("download_http_offset starting: url:"+str(url)+", start:"+str(start)+", offset:"+str(offset)+
                   ", filesize:"+str(filesize)+", readsize:"+str(readsize)+", filename:"+str(destfile))
        #Validate our start and offset
        start = int(start)
        if start < 0 or start > filesize:
            raise Exception('Invalid start for get_http_range, start:'+str(start))
        #calc range and expected byte length
        if offset:
            end = int(start)+int(offset-1)
            if end > filesize:
                end = filesize - 1
        else:
            end = filesize - 1 
        #calc total to check against later
        total = (end + 1) - start 
        #see if we can open our dest file before we download
        if destfile:
            destfile = self.make_path(destfile)
            dfile = open(destfile, 'w+')
        else:
            dfile = cStringIO.StringIO()
        #form our http request
        request = urllib2.Request(url)
        request.headers['Range'] = 'bytes=%s-%s' % (start, end)
        #open http connection
        remotefile = urllib2.urlopen(request)
        # If content length or range is not what we expected throw an error...
        # Note: content range in bytes is formated like: "byte <start>-<end>/<total bytes>
        range=remotefile.headers.get('Content-Range')
        clength = int(remotefile.headers.get('Content-Length'))
        print('Content-Range:' +str(range)+", Content-Length:"+str(clength) ) 
        if clength != total:
            raise Exception("Content-length:"+str(clength)+" not equal to expected total:"+str(total)+", is range supported on remote server?")
        #Now try to parse the ranges...
        try:
            rangestart, rangeend = re.search("\d+-\d+", range).group().split('-')
        except Exception, e:
            print "Couldn't derive rangestart and rangeend from string:"+str(range)+", err:"+str(e)
        if int(rangestart) != int(start) or int(rangeend) != int(end):
            raise Exception("Range request not met. (start:"+str(start)+" vs rangestart:"+str(rangestart)+") (end:"+str(end)+" vs rangeend:"+str(rangeend)+"), is range supported on remote server?") 
        #finally get the data and return it as a filelike cString object
        for data in iter(lambda: remotefile.read(readsize), ''):
            dfile.write(data)
        dfile.seek(0)
        return dfile
    
    
    def get_file_size(self,uri=None):
        '''
        Get remote file size for the http header
        '''
        url = uri or self.uri   
        site = urllib2.urlopen(url)
        size =  int(site.headers.get('Content-Length'))
        self.filesize = size
        return size
    
    def close(self):
        return 
        
            
        
            
            