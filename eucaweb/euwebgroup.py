'''
Created on Dec 14, 2011

@author: clarkmatthew
'''
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


# The Euwebgroup class allows users to create groups to put users in
# for testing purposes. These objects will be passed indentification
# information.
class Euwebgroup(object):
    # Constructor for the Euwebgroup
    def __init__ (self,
                  g_id="", #
                  name="", 
                  status="",
                  path=None,
                  row_xpath=None,
                  id_xpath=None,
                  name_xpath=None,
                  status_xpath=None
                  ):
        # Creates a group object with the specified criteria for
	# id, name, status, path, and row_path.
        self.id = g_id
        if (id_xpath):
            self.id_xpath = id_xpath
        
        self.name = name
        if (name_xpath):
            self.name_xpath= name_xpath
      
        self.status = status
        if (status_xpath):
            self.status_elm = status_xpath
        if (row_xpath):
            self.row_xpath = row_xpath
            
        if (path):
            self.path=path
        else:
            self.path="/"+self.name
            
    
     
    # Displays basic information about the group to the user         
    def printSelf(self):
        print "+++++++++++++++++GROUP++++++++++++++++++"
        print "Name:" + self.name
        print "ID:" + self.id
        print "Status" + self.status
