'''
Created on Nov 10, 2011

@author: clarkmatthew
'''
import time

class Webui_globals(object):
    def __init__(self):
        self.waitafterfail = 30
        
        #from main/start page
        #self.xUserLink='/html/body/div[3]/div[2]/div/div[2]/div/div[2]/div/div/table'
        self.xUserLink='/html/body/div[3]/div[2]/div/div[2]/div/div[2]/div/div/table/tbody/tr/td/a'
        
        
        #Left Nav links
        self.xLn_StartLink=     '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div/div[2]/div/div/div/div/div/div[2]'
        self.xLn_ServComp=      '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div/div[2]/div/div/div[2]/div/div/div[2]'
        self.xLn_IdMgmt=        '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[2]/div/div/div[2]'
        self.xLn_Accounts =     '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[2]/div[2]/div/div/div/div/div/div[2]'
        self.xLn_Groups=        '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div[2]'
        self.xLn_Users=         '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[2]/div[2]/div/div/div[3]/div/div/div[2]'
        self.xLn_Policies=      '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[2]/div[2]/div/div/div[4]/div/div/div[2]'
        self.xLn_Keys=          '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[2]/div[2]/div/div/div[5]/div/div/div[2]'
        self.xLn_Cert=          '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[2]/div[2]/div/div/div[6]/div/div/div[2]'
        self.xLn_ResMgmt=       '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[3]/div/div/div[2]'
        self.xLn_Images=        '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[3]/div/div/div[2]'
        self.xLn_VmTypes=       '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[3]/div[2]/div/div/div[2]/div/div/div[2]'
        self.xLn_UsageReport=   '/html/body/div[3]/div[2]/div/div[5]/div/div[3]/div/div/div/div/div/div/div[3]/div[2]/div/div/div[3]/div/div/div[2]'
        
        #login page links
        self.xSignUp= '/html/body/div[3]/div[2]/div/div[2]/div/a'
        self.AccountSignUpInvalidName ='invalid character for account name'
        self.AccountSignUpInvalidEmail = 'not look like a valid email address'
        self.AccountSignUpPassNoMatch = 'do not match'
        self.AccountSignUpPassTooShort = 'length must be at least'
        self.AccountSignUpSuccess="signup succeeded"
        self.AccountSignUpError = "Failed to complete the account signup"
        self.PasswordResetTxt = "reset request is sent"
        self.PasswordTxt = "Password"
        self.PasswordResetForm = "enter your new password"
        self.PasswordRestSuccess = 'password is successfully reset'
        self.FirstTimeLogin ='First time login'
        
        
        #general page locations
        self.xPage='//*'
        self.xLeftNav='/html/body/div[3]/div[2]/div/div[5]'    
        self.xRightNavTable = '/html/body/div[3]/div[2]/div/div[7]/div/div[4]/div/div/table'
        self.xRightNavTableRow1 = self.xRightNavTable+'/tbody/tr'
        self.xRighNavSaveButton = '/html/body/div[3]/div[2]/div/div[7]/div/div[3]/div/table/tbody/tr/td/button'
        self.xLogButton = '/html/body/div[3]/div[2]/div/div[3]/div/div[4]/div/a/span'
        self.xRow1LogMsg = '/html/body/div[3]/div[2]/div/div[4]/div/div/table/tbody/tr/td[3]'
        self.xLogMessage = '/html/body/div[3]/div[2]/div/div[3]/div/div/div'
        
        #Accounts Page           
        self.AccountsTopNavButtonNewAccount ='/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td'
        self.AccountsTopNavButtonDelAccount ='/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[2]'
        self.AccountsTopNavButtonNewUser=    '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[4]'
        self.AccountsTopNavButtonNewGroup= '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[5]'
        self.AccountsTopNavButtonAddPolicy = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[7]'
        self.AccountsTopNavButtonApprove = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[9]'
        self.AccountsTopNavButtonReject = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[10]'
        #accounts table locations
        self.xAccountsTable='/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[3]/div/div[2]/div/div[3]/div/div/div/table'
        self.xAccountsRow1=self.xAccountsTable+'/tbody/tr'
        self.xAccountsRow1Id=self.xAccountsRow1+'/td'
        #accounts right nav locations
        self.xAccountsRightNavTable= self.xRightNavTable
        self.xAccountRightNavRow1=self.xAccountsRightNavTable+'/tbody/tr'
        self.xAccountForwardButton='/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[4]/img'
        #account page range is the current page / pages available between forward and reverse buttons
        self.xAccountPageRange ='/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[3]'
        self.AccountsRightNav_Name = 'Name'
        self.AccountsRightNav_RegStatus = 'Registration status'
        self.StatusRegistered = "REGISTERED"
        self.StatusConfirmed = "CONFIRMED"
        self.StatusApproved = "APPROVED"
        
        self.urlSearchAccountByName='#account:name='
        self.urlSearchAccountById='#account:id='
        
        
        #Users
        self.UsersTopNavButtonDeleteUser = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td'
        self.UsersTopNavButtonAddToGroup = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[3]'
        self.UsersTopNavButtonRemoveFromGroup = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[4]'
        self.UsersTopNavButtonAddPolicy = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[6]'
        self.UsersTopNavButtonAddKey = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[7]'
        self.UsersTopNavButtonAddCert = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[8]'
        self.UsersTopNavButtonApprove = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[10]'
        self.USersTopNavButtonReject = '/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[11]'
        self.xUsersTable='/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[3]/div/div[2]/div/div[3]/div/div/div/table'
        self.xUsersRow1 = self.xUsersTable+'/tbody/tr'   
        self.xUsersRow1Id= self.xUsersRow1+'/td' 
        self.urlSearchUserByName='#user:name='
        self.urlSearchUserByAccount='#user:account='
        self.xUsersRightNavTable = self.xRightNavTable
        self.xUsersRightNavRow1 = self.xRightNavTableRow1
        self.xUserEnabledTxt = "true"
        self.xUserDisabledTxt = "false"
        self.UsersRightNav_Enabled ='Enabled'
        self.UsersRighNav_Password = 'Password'
        #self.ApproveButton = '' Use click link by text...
        #self.RejectButton = ''
        
        #groups
        #self.xGroupRow1Id'/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[3]/div/div[2]/div/div[3]/div/div/div/table/tbody/tr/td'
        self.xGroupTable='/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[3]/div/div[2]/div/div[3]/div/div/div/table/'
        self.xGroupRow1=self.xGroupTable+'/tbody/tr'
        self.xGroupRow1Id=self.xGroupRow1+'/td'
        self.urlSearchGroupByName='#group:name='
        
        #vmtypes
        self.xVmTypeTable='/html/body/div[3]/div[2]/div/div[8]/div/div[3]/div/div[2]/div/div[2]/div/div[3]/div/div/div/table'
        self.xVmTypeRow1=self.xVmTypeTable+'/tbody/tr'
        self.xVmTypeRow1Id=self.xVmTypeRow1+'/td'
        self.vmTypeRightNavNameTxt="Name"
        self.vmTypeRightNavCpuTxt="CPUs"
        self.vmTypeRightNavMemTxt='Memory (MB)'
        self.vmTypeRightNavDiskTxt='Disk (GB)'
        self.urlSearchVmType='#vmtype:'
        
        #keys
        self.xaddKeyPopupKey= '/html/body/div[6]/div/table/tbody/tr[2]/td[2]/div/div/table/tbody/tr[2]/td/div/div/table/tbody/tr/td'
        self.xaddKeyPopupUser= '/html/body/div[6]/div/table/tbody/tr[2]/td[2]/div/div/table/tbody/tr[2]/td/div/div/table/tbody/tr/td[2]'
        self.xaddKeyOkButton='/html/body/div[6]/div/table/tbody/tr[2]/td[2]/div/div/table/tbody/tr[3]/td/a'
        self.urlSearchKeyID='#key:id='
        
        
        #Text used to verify pages have loaded...
        self.StartTxt='START GUIDE'
        self.ServCompTxt='SERVICE COMPONENTS'
        self.AccountsTxt='ACCOUNTS'
        self.GroupsTxt='GROUPS'
        self.UsersTxt='USERS'
        self.PoliciesTxt='ACCESS POLICIES'
        self.KeysTxt='ACCESS KEYS'
        self.CertTxt='X509 CERTIFICATES'
        self.ImagesTxt='VIRTUAL MACHINE IMAGES'
        self.VmTypesTxt='VIRTUAL MACHINE TYPES'
        self.UsageReportTxt='USAGE REPORT'
        self.rightNavTxt = 'PROPERTIES'
        
            
    def testCase(self,results, method, *args):
        name = method.__name__
        print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++"
        self.printStarting()
        tstr = "TEST("+name+")"
        print "\n\n\nRunning " + tstr
        time.sleep(5)
        try: 
            method(*args)
            print  tstr+": PASSED"
            self.printPassed()
            results.append((tstr," PASSED", ""))
        except testCaseSkipped, se:
            reason = str(se)
            print tstr+": SKIPPED:" +reason
            self.printPassed()
            results.append((tstr," SKIPPED", ""))
        except Exception, e:
            reason = str(e)
            print tstr+": FAILED:" +reason
            self.printFailed()
            print "sleeping for ("+str(self.waitafterfail)+")"
            time.sleep(self.waitafterfail)
            results.append((tstr," FAILED", reason))
    
    def printResults(self,results):
        print "\n\n\n"
        for test in results:
            name,res,reason = test
            print '{0:55} ==> {1:6}:{2}'.format(name,res,reason)
            
    def printStarting(self):
        print "\n"
        print '''
         _              _   _              
        | |            | | (_)             
     ___| |_  __ _ _ __| |_ _ _ __   __ _  
    / __| __|/ _` | '__| __| | '_ \ / _` | 
    \__ \ |_| (_| | |  | |_| | | | | (_| | 
    |___/\__|\__,_|_|   \__|_|_| |_|\__, | 
                                     __/ | 
                                    |___/  
                                        
    '''
    def printClosing(self):
        print "\n"
        print ''' 
     _____ _           _ 
    /  __ \ |         (_)
    | /  \/ | ___  ___ _ _ __   __ _ 
    | |   | |/ _ \/ __| | '_ \ / _` |
    | \__/\ | (_) \__ \ | | | | (_| |
     \____/_|\___/|___/_|_| |_|\__, |
                                __/ |
                               |___/ 
    
    '''
        print "\n"
    
    
    
    def printPassed(self):
        print "\n"
        print ''' 
    ______  ___  _____ _____ ___________  
    | ___ \/ _ \/  ___/  ___|  ___|  _  \ 
    | |_/ / /_\ \ `--.\ `--.| |__ | | | | 
    |  __/|  _  |`--. \`--. \  __|| | | | 
    | |   | | | /\__/ /\__/ / |___| |/ /  
    \_|   \_| |_|____/\____/\____/|___/   
    
    '''
        print "\n"
    
    
    def printFailed(self):
        print "\n"
        print '''
    ______ ___  _____ _      ___________ 
    |  ___/ _ \|_   _| |    |  ___|  _  \ 
    | |_ / /_\ \ | | | |    | |__ | | | | 
    |  _||  _  | | | | |    |  __|| | | | 
    | |  | | | |_| |_| |____| |___| |/ /  
    \_|  \_| |_/\___/\_____/\____/|___/  
                                         
    '''
        print "\n"        
        
class testCaseSkipped(Exception):
    def __init__(self, value):
        self.value = value
    def __str__ (self):
        return repr(self.value)
    
    
    
