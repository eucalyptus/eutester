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
'''
Created on May 11, 2012
@author: clarkmatthew

Simple utility to read a given config file and parse out the configuration. 
Uses python's Config Parser but includes some utils to support legacy qa config files,
and file operations on local and remote machines containing keypair values.
To use this utility, the config file given must use the following format:
[prefix]key=value

example:
Add the following lines to a file called /tmp/config.txt
Note: 
This example is using the legacy config with ip, distro, and component info. 

>cat /tmp/config.txt
    1.1.1.1   CENTOS  5.7     64      REPO [CLC WS]
    1.1.1.2   CENTOS  5.7     64      REPO [NC00]
    
    [mytest]
    volumes=2
    image=centos.img
    
    [joestest]
    image=ubuntu.img
    name=joe
    iterations=3
    output=/tmp/joesoutput.txt


To retrieve config info from this file from within a test:
>conf = EuConfig(filename='/tmp/config.txt')
>myimage = conf.get_config('mytest','image')
>joesimage = conf.get('joestest','image')
>
>print myimage
 centos.img
 
>print conf.legacybuf
 1.1.1.1   CENTOS  5.7     64      REPO [CLC WS]
 1.1.1.2   CENTOS  5.7     64      REPO [NC00]


'''
import re
import io
import os
import ConfigParser
import time
import hashlib



class File_Util():
    #Possible file edit actions
    ADDTOLINE = 'ADDTOLINE'
    SWAP = 'SWAP'
    ADD = 'ADD'
    REMOVE = 'REMOVE'

    def __init__(self,
                 filepath,
                 ssh=None,
                 remove_blank_lines=True,
                 verbose=False):
        self.filepath = filepath
        self.lines = []
        self.ssh = ssh
        self.verbose = verbose
        self.remove_blank_lines = remove_blank_lines
        self.md5sum = None
        self.update()

    def file_open(self, filepath, read=True, write=False, create=True, flags=None):
        flags = flags or ""
        if not flags:
            if read:
                flags += 'r'
            if write:
                flags += 'w'
                if create:
                    flags += "+"
        if self.ssh:
            if not self.ssh.sftp:
                self.ssh.open_sftp()
            fileobj= self.ssh.sftp.file(filepath,flags)
        else:
            fileobj = open(filepath,flags)
        return fileobj


    def file_replace(self, from_path, to_path):
        if self.ssh:
            self.ssh.sys('mv ' + str(from_path) + " " + str(to_path))
        else:
            os.remove(to_path)
            os.rename(from_path, to_path)

    def get_md5(self, blocksize=65536):
        my_file = self.file_open(self.filepath, flags='rb')
        md5 = hashlib.md5()
        buf = my_file.read(blocksize)
        while len(buf) > 0:
            md5.update(buf)
            buf = my_file.read(blocksize)
        my_file.close()
        self.md5sum = md5.hexdigest()
        return md5.hexdigest()


    def has_changed(self):
        if self.md5sum != self.get_md5():
            return True
        else:
            return False

    def sanitize(self,dirty_string):
        clean_string = ""
        for c in dirty_string:
            if re.match('\W',c):
                clean_string += '\\' + c
            else:
                clean_string += c
        return clean_string

    def print_file(self, printmethod=None):
        for line in self.lines:
            if printmethod:
                printmethod(line.strip())
            else:
                print line.strip()

    def search_in_lines(self, search_pattern, after_pattern=None):
        if not after_pattern:
            found_after = True
        else:
            found_after = False
        for line in self.lines:
            if not found_after:
                if re.search(after_pattern, line):
                    found_after = True
            if found_after and re.search(search_pattern, line):
                return line
        return None

    def match_in_lines(self, match_pattern, after_pattern):
        if not after_pattern:
            found_after = True
        else:
            found_after = False
        for line in self.lines:
            if not found_after:
                if re.match(after_pattern, line):
                    found_after = True
            if found_after and re.match(match_pattern, line):
                return line
        return None

    def update(self, retries=3):
        while retries:
            retries -= 1
            self.lines = self.get_file_lines()
            if self.lines:
                self.md5sum = self.get_md5()
                return
            time.sleep(2)
        print 'No lines gathered in update'


    def get_file_lines(self):
        lines = []
        cfile = None
        try:
            cfile = self.file_open(self.filepath,read=True)
            cfile.seek(0)
            for line in cfile.readlines():
                if line.strip() or not self.remove_blank_lines:
                    lines.append(line)
        except Exception, e:
            if cfile:
                cfile.close()
            raise Exception('Error in get_file_lines: ' + str(e))
        finally:
            if cfile:
                cfile.close()
        return lines

    def file_edit_line(self,
                    new_line,
                    action = None,
                    search_pattern=None,
                    after_pattern=None,
                    single_action=True,
                    tempfilepath=None):
        if self.verbose:
            print "Starting file_edit_line..."
        tempfilepath = tempfilepath or str(self.filepath)+str('.tmp')
        tempfile = self.file_open(tempfilepath, write=True, create=True)
        self.update()
        updated = False
        if not action:
            raise Exception('file_edit_line needs File_Util action provided')
        action = str(action).upper()
        if not hasattr(self, action):
            raise Exception('Action:' + str(action) + ' not found as valid action?')
        if not after_pattern:
            start_write = True
        else:
            start_write = False
        #If no search criteria is specified, just write the line to the file...
        if start_write and not search_pattern:
            myfile = open(self.filepath, 'w')
            myfile.write(new_line)
            myfile.close()
            print new_line
        #Iterate through file, when search patterns have been satisfied, write new_line...
        try:
            for line in self.lines:
                if updated and single_action:
                    tempfile.write(line)
                    continue
                line = line.strip()
                if not start_write:
                    if re.search(after_pattern, line):
                        start_write = True
                if start_write:
                    if not search_pattern or re.search(search_pattern, line):
                        print "Found search pattern:" + str(search_pattern)
                        if action == File_Util.ADD:
                            if self.verbose: print "OLD:" + str(line)
                            line = str(line) + "\n" + new_line
                            if self.verbose: print "NEW:" + str(line)
                            updated = True
                        elif search_pattern and action == File_Util.ADDTOLINE:
                            if self.verbose: print "OLD:" + str(line)
                            line = str(line) + new_line
                            if self.verbose: print "NEW:" + str(line)
                            updated = True
                        elif search_pattern and action == File_Util.SWAP:
                            if self.verbose: print "OLD:" + str(line)
                            line = new_line
                            if self.verbose: print "NEW:" + str(line)
                            updated = True
                        elif search_pattern and action == File_Util.REMOVE:
                            if self.verbose: print "OLD:" + str(line)
                            if self.verbose: print "NEW:"
                            updated = True
                            continue
                if self.verbose: print "writing line:" +str(line)
                tempfile.write(line + "\n")
            if updated:
                self.file_replace(tempfilepath,self.filepath)
        except Exception, e:
            print "Error when editing file:" + str(e)
        finally:
            tempfile.close()
            if updated:
                self.update()



    def swap_existing_line(self, search_pattern, new_line, after_pattern=None ):
        return self.file_edit_line(new_line=new_line,
                                   search_pattern=search_pattern,
                                   after_pattern=after_pattern,
                                   action=File_Util.SWAP)

    def add_new_line(self, new_line, after_pattern=None, over_write=False):
        return self.file_edit_line(new_line=new_line,
                                   after_pattern=after_pattern,
                                   action=File_Util.ADD)
    def stat_file(self):
        if self.ssh:
            return self.ssh.sftp.stat(self.filepath)
        else:
            return os.stat(self.filepath)

    def add_to_existing_line(self, search_pattern,values_to_add, after_pattern=None):
        return self.file_edit_line(new_line=values_to_add,
                                   search_pattern=search_pattern,
                                   after_pattern=after_pattern,
                                   action=File_Util.ADDTOLINE)

    def remove_existing_line(self, search_pattern,after_pattern=None):
        return self.file_edit_line(new_line='',
                                   search_pattern=search_pattern,
                                   after_pattern=after_pattern,
                                   action= File_Util.REMOVE)



class Config_Item():
    def __init__(self, name, value, config_section):
        self.name = name
        self.value = value
        self.search_pattern = str(self.name) + "\s*="
        self.config_section = config_section

    def update(self):
        self.config_section = self.config_section.update()


    def config_file_set_this_line(self,value, quoted=True):
        new_value = str(value)
        if quoted:
            new_value = '"' + new_value.strip('"') + '"'
        new_value = str(self.name) + "=" + str(new_value)
        ret = self.config_section.config_file_swap_line(self.search_pattern, new_line=new_value)
        self.update()
        return ret

    def config_file_add_to_this_line(self, value_to_add):
        ret = self.config_section.config_file_add_to_existing_line(search_pattern=self.search_pattern, value_to_add=value_to_add)
        self.update()
        return ret

    def config_file_remove_this_line(self):
        ret = self.config_section.config_file_remove_line(search_pattern=self.search_pattern)
        self.update()
        return ret

    def __str__(self):
        return "SECTION:" + str(self.config_section.name) + ", VALUE:" + str(self.value)



class Config_Section():
    def __init__(self, name, config_manager, strip='"'):
        self.name = name
        self.config_manager = config_manager
        self.strip = strip
        self.file_util = self.config_manager.file_util
        self.section_pattern = self.get_section_pattern()
        self.update_attributes_for_section()


    def update(self):
        if self.config_manager.file_util.has_changed():
            self.config_manager.update()
            self.update_attributes_for_section()
        return self

    def get_item(self, name):
        item = None
        if hasattr(self, name):
            item = getattr(self, name)
        return item

    def get_section_pattern(self):
        if self.config_manager.has_a_section():
            section_pattern = '\[\s*' + str(self.name) + '\s*\]'
        else:
            section_pattern = None
        return section_pattern

    def update_attributes_for_section(self):
        existing_items = self.get_all_items()
        for item in self.config_manager.config.items(self.name):
            item_name = item[0]
            existing_item = self.get_item(name=item_name)
            if self.strip:
                value =  str(item[1]).strip(self.strip)
            else:
                value = item[1]
            self.add_item_to_section(item_name,value)
            if existing_item:
                existing_items.remove(existing_item)
        if existing_items:
            self.remove_all_items(items=existing_items)

    def write_new_item_to_section_in_config_file(self,key, value):
        new_line = str(key) + "=" + '"' + str(value).strip('"') + '"'
        self.config_file_add_new_line_to_section(new_line=new_line)

    def add_item_to_section(self, config_item_name, value):
        if hasattr(self, config_item_name):
            item = getattr(self, config_item_name)
            if not isinstance(item, Config_Item):
                raise Exception('Conflicting attribute name:' + str(config_item_name))
            item.__init__(config_item_name, value, self)
        else:
            new_item = Config_Item(config_item_name, value, self)
            setattr(self, config_item_name, new_item)

    def config_file_add_to_existing_line(self, search_pattern, value_to_add):
        return self.file_util.add_to_existing_line(search_pattern=search_pattern,
                                            value_to_add=value_to_add,
                                            after_pattern=self.section_string)


    def config_file_swap_line(self, search_pattern, new_line):
        return self.file_util.swap_existing_line(search_pattern=search_pattern,
                                          new_line=new_line,
                                          after_pattern=self.section_pattern)

    def config_file_remove_line(self, search_pattern):
        return self.file_util.remove_existing_line(search_pattern=search_pattern, after_pattern=self.section_pattern)

    def config_file_add_new_line_to_section(self, new_line, over_write=True):
        return self.file_util.add_new_line(new_line=new_line,
                                    after_pattern=self.section_pattern,
                                    over_write=over_write)


    def get_all_items(self, item_name=None):
        items = []
        for attr in self.__dict__:
            if isinstance(self.__dict__[attr], Config_Item):
                if not item_name or (item_name == attr):
                    items.append(self.__dict__[attr])
        return items

    def get_item(self,name):
        item = None
        items = self.get_all_items(item_name=name)
        if item:
            item = item[0]
        return item

    def remove_all_items(self, item_name=None, items=None):
        items = items or self.get_all_items(item_name=item_name)
        for item in items:
            delattr(self, item.name)


class EuConfig():
    
    def __init__(self,
                 filename='../input/2btested.lst',
                 file_util=None,
                 ssh=None,
                 config_lines=None,
                 debugmethod=None,
                 verbose=True,
                 default_section_name='DEFAULTS',
                 auto_detect_memo_section=True,
                 make_section_attrs=True,
                 legacy_qa_config=False,
                 preserve_option_case=True,
                 strip_values = '"'):
        self.config = None
        self.preserve_option_case = preserve_option_case
        self.legacy_qa_config = legacy_qa_config
        self.file_util = file_util
        self.ssh = ssh
        self.auto_detect_memo_section=auto_detect_memo_section
        self.debugmethod = debugmethod
        self.make_section_attrs = make_section_attrs
        self.strip_values = strip_values
        self.filename = filename
        self.default_section_name = default_section_name or os.path.basename(self.filename).replace('.','_')
        self.verbose = verbose

        if not self.file_util:
            self.file_util = self.create_file_util_from_file(filepath = filename, ssh=ssh, verbose=False)

        #read the file into a list of lines
        self.lines = config_lines or self.file_util.lines
        self.config = None
        if self.auto_detect_memo_section and self.has_legacy_memo_section_marker(lines=self.lines):
            self.legacy_qa_config=True
        self.update()



    def check_and_add_default_section(self, default_section_name=None):
        default_section_name = default_section_name or self.default_section_name
        if self.has_a_section():
            return
        default_section_name = default_section_name or self.default_section_name
        default_section = '[' + str(default_section_name) + ']\n'
        self.lines.insert(0, default_section)

    def has_legacy_memo_section_marker(self, lines=None):
        lines = lines or self.lines
        for line in lines:
            if re.match("^MEMO\s*$", line):
                return True
        return False

    def has_a_section(self):
        for line in self.lines:
            if re.match("^\[\]+",  line):
                return True
        return False

    def update(self,lines=None):

        #read/re-read the file into a list of lines
        if lines:
            self.lines = lines
        else:
            self.file_util.update()
            self.lines = self.file_util.lines
            if not self.legacy_qa_config:
                self.check_and_add_default_section()

        #parse out any legacy config into a separate buffer (to support older test config formats)
        self.legacybuf = self.get_legacy_config()

        #parse out remaining non-legacy config into another buffer
        self.configbuf = self.get_config_buf()

        #create our configParser object using the config buffer
        self.config = None

        self.populate_config_parser_from_buf(buf=self.configbuf)


    @classmethod
    def create_file_util_from_file(cls, filepath, ssh=None, verbose=False):
        """
        Creates either a File_Util obj, working on either a local or remote file (if ssh is provided).
        :param filepath: string representing the local or remote file path
        :param ssh: eutester ssh_connection obj if file is remote
        :return: File_Util obj
        """
        file_util = File_Util(filepath=filepath, ssh=ssh)
        return file_util


    def add_new_item_to_config_file_under_section(self,section_name, config_item_name, value):
        self.debug('Attempting to add new config item:\n' + \
                    'config file:' +str(self.filename) + \
                    'section:' + str(section_name) + \
                    'config_item_name:' + str(config_item_name) + \
                    'value:' + str(value))
        
    def get(self,section,key):
        return self.config.get(section,key)


    def populate_config_parser_from_buf(self,
                                        buf=None,
                                        default_section_name=None,
                                        make_section_attrs=None,
                                        strip_values=None):
        #create our configParser object using the config buffer
        default_section_name = default_section_name or self.default_section_name
        make_section_attrs = make_section_attrs or self.make_section_attrs
        strip_values = strip_values or self.strip_values
        self.config = ConfigParser.RawConfigParser()
        if self.preserve_option_case:
            self.config.optionxform = str
        buf = buf or self.configbuf
        default_section_name=default_section_name or self.default_section_name
        try:
            self.config.readfp(io.BytesIO(buf))
        except ConfigParser.MissingSectionHeaderError, mshe:
            self.debug('Caught MissingSectionHeaderError')
            #A file with key pair format but no sections may have been fed in...?
            if default_section_name:
                buf = '[' + str(default_section_name) + ']\n' + str(buf)
                return self.create_config_parser_from_buf(buf=buf, create_default_section=False)
            else:
                raise mshe
        if make_section_attrs:
            self.make_sections(strip=strip_values)


        
    def debug(self, msg):
        if self.verbose:
            if self.debugmethod is not None:
                self.debugmethod(str(msg))
            else:
                print(str(msg))
        
        
    def get_legacy_config(self, lines=None):
        '''
        Gather all lines  from the given config until a section header is reached
        In order to be backwards compatible with previous configuration files
        will return a buffer of file read until the first section header
        '''
        buf=""
        if lines is None:
            lines = self.lines
        for line in lines:
            #read file until first section  header
            if re.match("^\[", line):
                #self.debug("Found section header, returning buf")
                return buf
            else:
                #filter out comments and blank lines
                if re.match("^\s+#",line) or re.match("^\s+$",line):
                    #self.debug("Ignoring legacy line:"+str(line))
                    continue
                else:
                    #self.debug("Adding line to legacy buf:"+str(line))
                    buf=buf+line
        return buf

    def uncomment_line(self, config_item):
        new_conf = []
        for line in self.lines:
            if re.match("^\s+#",line) and re.search(config_item,line):
                #self.debug("Ignoring legacy line:"+str(line))
                new_conf.append(line.strip('#'))
            else:
                new_conf.append(line)
        self.lines = new_conf
    
    def get_config_buf(self,lines=None, default_section_name=None):
        '''
        Gather config lines into list. 
        To support legacy config, will exclude all lines read prior to detecting a section header. 
        Will ignore blank lines and lines starting with "#" representing comments 
        '''
        buf=""
        start=False
        got_section = False
        if lines is None:
            lines = self.lines
        for line in lines:
            if re.match("^MEMO\s+", line):
                line = '['+str(line).strip()+']\n'
                got_section = True
            if re.match("^END_MEMO", line):
                continue
            #read file until first section  header
            if not start:
                if re.match("^\[", line):
                    #self.debug("Found fist section header, start reading in config buff")
                    got_section = True
                    buf=buf+line
                    start=True
            else:
                if re.match("^\s*#",line) or re.match("^\s+$",line) or not re.search("=",line):
                    #self.debug("Ignoring line for config buf:"+str(line))
                    continue
                else:
                    #self.debug("Adding line to config buff:"+str(line))
                    if not line.endswith('\n'):
                        line = line+"\n"
                    buf=buf+line

        return buf
                

    def make_sections(self, strip='"'):
        '''
        Creates section objects within this euconfig instance. These are dynamic for python console dev/debugging use,
        the use of these in testcases should be avoided.
        Example: The machine classes may have a file called eucalyptus_conf and create a section '[eucalyptus_conf]'
        This will add the section to self.config.sections, as well as create a Config_Section() object with attributes
        for each item which contain that item's value.
        For a machine called 'clc' values out of this config file can be access like this...
            >print clc.config.eucalyptus_conf.hypervisor
            > kvm

            >print clc.config.eucalyptus_conf.cloud_opts
            >-Debs.storage.manager=SANManager -Debs.san.provider=NetappProvider --debug
        '''
        if not self.config or not self.config.sections():
            self.debug('No config sections for:'+str(self.filename))
            return
        existing_sections = self.get_all_sections()
        #Check for any new sections, update any existing sections, and remove any that are no longer found
        for section in self.config.sections():
            self.debug('Creating/updating section: ' + str(section))
            existing_section = self.get_section(section)
            if existing_section:
                self.debug('Updating Existing Section: ' + str(section))
                existing_section.update_attributes_for_section()
                existing_sections.remove(existing_section)
            else:
                self.debug('Adding section:' + str(section))
                new_section = Config_Section(section,self, strip=strip)
                setattr(self, section, new_section)
        #Remove any pre-existing sections that no longer exist
        if existing_sections:
            self.remove_all_sections(sections=existing_sections)

    def get_all_sections(self, section_name=None):
        sections = []
        for attr in self.__dict__:
            if isinstance(self.__dict__[attr], Config_Section):
                if not section_name or (section_name == attr):
                    sections.append(self.__dict__[attr])
        return sections

    def get_section(self,name):
        section = None
        sections = self.get_all_sections(section_name=name)
        if sections:
            section = sections[0]
        return section

    def remove_all_sections(self, section_name=None, sections=None):
        sections = sections or self.get_all_sections(section_name=section_name)
        for section in sections:
            if not section_name or section.name == section_name:
                self.debug('Removing section:' +str(section.name))
                delattr(self, section.name)

    
        
            
        
        