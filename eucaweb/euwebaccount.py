'''
Created on Nov 15, 2011

@author: clarkmatthew
modified by Coady LaCroix
'''
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


# The Euwebaccount class allows the user to create web account
# objects for testing purposes. These objects can be passed
# information for identification. 
class Euwebaccount(object):
    # Constructor for Euwebaccount 
    def __init__ (self,
                  a_id="", #
                  name="", 
                  status="",
                  row_xpath=None,
                  id_xpath=None,
                  name_xpath=None,
                  status_xpath=None
                  ):
	# Creates an account object  with the specified criteria
	# for id, name, status, and row_path
        self.id = a_id
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
           
  
    # Displays basic information about the account to the user        
    def printSelf(self):
        print "+++++++++++++++++ACCOUNT++++++++++++++++++"
        print "Name:" + self.name
        print "ID:" + self.id
        print "Status" + self.status
                        
            
            
