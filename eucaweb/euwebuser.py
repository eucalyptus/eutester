'''
Created on Nov 11, 2011

@author: clarkmatthew
'''
import random,string, time
#import eulogger
#logger = eulogger.Eulogger()
#log = logger.log


##########################################################################################            
##########################################################################################

# The Euwebuser class allows users to create a personal account for 
# testing purposes. These objects will pass information used for 
# identification.
class Euwebuser(object):
    
    # Constructor for the Euwebuser    
    def __init__ (self, 
                  account="", 
                  user="", 
                  passwd="", 
                  credpath="", 
                  email = "", 
                  prefix="",
                  path="",
                  uid="",
                  enabled="",
                  regstatus="",
                  makerandom=True):
        
            print "Init euwebuser...."
            print("creating user...")
            #If the ID is not provided use the username, if the user is not provided create a random one
	    # Creates a user object with the specified criteria for
	    # account, user, passwd, credpath, email, prefix, and path.
            self.account = account
            self.user = user
            self.passwd = passwd
            self.credpath = credpath
            self.email = email
            self.prefix = prefix
            self.path = path
            self.id = uid
            self.enabled = enabled
            self.status = regstatus
            self.rid = "NA"
            
            if (makerandom == True):
                try:
                    rand = random.Random()
                    time.sleep(1)# just to make sure seed is unique
                    self.rid = str(rand.randint(1, 100000000))
                except Exception, e:
                    print "Couldn't gen random id use time.clock instead:" + str(e)
                    rid = str(time.clock())
                
                #UID should be created by the CLC not the user
                self.id = uid
                    
                if (account != ""):
                    if (account == "random"):
                        self.account = prefix+"account-"+self.rid
                    else:
                        self.account = account
                else:
                    self.account = prefix+"account-"+self.rid
                
                if (user):
                    if (user == "random"):
                        self.user = prefix+self.rid
                    else:
                        self.user = user
                else:
                    self.user = "admin"
                
                if (passwd):
                    self.passwd = passwd
                else:
                    self.passwd = "passwd"+self.rid 
                
                if (credpath):
                    self.credpath = credpath
                else:
                    self.credpath = self.user+"_dir"
                    
                if (email):
                    self.email = email
                else:
                    self.email = self.user+'@'+self.account
                
            
    # Displays basic information about the user                     
    def printUser(self):
        print("+++++++++++++PRINT USER+++++++++++++++++++++")
        print("id:"+self.id)
        print("account:"+self.account)
        print("user:"+self.user)
        print("passwd:"+self.passwd)
        print("credpath:"+self.credpath)
        print("email: " +self.email)
        print("enabled:"+self.enabled)
        print("regstat:"+self.status)
        print("++++++++++++++++++++++++++++++++++++++++++++")
        
        
        
        
        
        
        
