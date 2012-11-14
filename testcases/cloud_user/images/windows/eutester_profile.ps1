#### FUNCTIONS RELATED TO ALL TESTS ####
function Eutester-New-Euca-QA {
     param ($hostname)
     write-debug "Eutester-New-Euca-QA starting..."
     $Global:DebugPreference="Continue"                      
     [string] $ret = Eutester-Authorize-Host $hostname
     if($ret -notmatch "SUCCESS"){ return "Can't authorize the destination $hostname"}
     return "SUCCESS"
}

function Eutester-Echo{
    param ($word)
    write-debug $word
    return $word
}

function Eutester-exit{
    param ($code)
    exit $code
}

function Eutester-Authorize-Host {
    param ($hostname)
    write-debug "Eutester-Authorize-Host starting..."
    if(!($hostname)){ throw "hostname is not specified"}
    
    $authcmd = "winrm s winrm/config/client `'@{TrustedHosts=`"$hostname`"}`'"
    invoke-expression $authcmd
    write-debug "Eutester-Authorize-Host returning Succces"
    return "SUCCESS"
}

## Eutester-this function will be called before every other win VM test
function Eutester-Test-Euca-Login {    
    param ($hostname, $password)
    write-debug "Eutester-Test-Euca-Login starting..."
    $retry = 5;
    $s=$null;
    $attempt = 0
    while($retry-- -ge 0)
    {   
        $attempt++
        write-debug "Login attempt: $attempt "  
        try{
            $s = Eutester-Get-RMSession -hostname $hostname -username "Administrator" -password $password
            if($s){
                write-debug "Login to $hostname succeeded after $attempt attempts" 
                break;  
            }else{ 
                write-debug "Login failed on attempt $attempt, $retry-1 attempts remaining"
                start-sleep -seconds 3
            }    
        }catch {
            write-debug "Login failed on attempt $attempt, $retry-1 attempts remaining"  
            start-sleep -seconds 3
        }
    }
    
    if($s){
        return "SUCCESS" 
    }else{
        return "Session not created: $_"
        }
}

function Eutester-Remove-RMSession {
    param ($hostname)
    write-debug "Eutester-Remove-RMSession starting..."
    $rand = New-Object system.random
    $randNum = $rand.next(20)
    $arr=Get-PSSession $hostname 

    foreach($s in $arr){
        try{        
            Remove-PSSession $s            
        }catch{
            
        }
    }
    return "SUCCESS"
}

function Eutester-Get-RMSession {
    param ($hostname, $username="Administrator", $password)  
    write-debug "Eutester-Get-RMSession starting..."
    if(!$EUCA_SESSION){ 
        if((Eutester-New-Euca-QA $hostname) -ne "SUCCESS") { throw "Can't authorize the destination host for RM session"}
    }
    
    $secureStr = ConvertTo-SecureString -String $password -asplaintext -force
    if(!($username.Contains("\"))){$username = "$hostname\$username"}
    $cred = new-object system.management.automation.pscredential $username, $secureStr
    $rand = New-Object system.random
    $randNum = $rand.next(20)
    $arr=Get-PSSession $hostname 
    if(!($arr))
    {
       write-debug "Session was not available, so new pssession is being created..."
       $randNum = $rand.next(20)   
        $session = new-PSSession -computername $hostname -credential $cred        
        if(!($session))
        {
            write-debug "Failed to create session"
            if($error[0].Exception.Message.Contains("Access is denied")){   throw "Password was wrong"}
            elseif($error[0].Exception.Message.Contains("The WinRM client cannot process the request"))
            {   throw "Host is not available for winrm"}
            else{   throw "Unknown error: "+$error[0].Exception.Message}                
        }
        write-debug "Session creation successful"
        new-variable -name EUCA_SESSION -value $true -option ReadOnly -visibility Public -scope Script
        new-variable -name EUCA_HOSTNAME -value $hostname -option ReadOnly -visibility Public -scope Script
        new-variable -name EUCA_PASSWORD -value $password -option ReadOnly -visibility Public -scope Script
        new-variable -name EUCA_USERNAME -value $username -option ReadOnly -visibility Public -scope Script
        
        $session
    }else{
        foreach($s in $arr){
            if($s.State -ne "Opened")
            {
                Remove-PSSession $s
            }else{
                return $s
            }
        }
        # there's no open session 
        get-rmsession $hostname $username $password
    }
}

#### FUNCTIONs RELATED TO HYPERV QA ####
function Eutester-New-Hyperv-Deploy{
     param ($hostname, $password="foobar")
     $Global:DebugPreference="Continue"                      
     [string] $ret = Eutester-Authorize-Host $hostname
     if($ret -notmatch "SUCCESS"){ return "ERROR: Can't authorize the destination $hostname"}
     
    try{
        $s = Eutester-Get-RMSession -hostname $hostname -username "Administrator" -password $password
        if($s){ return "SUCCESS" }
        else { return "ERROR: Session not created" }    
    }catch {  
        return $_   # return error text
    }
    
     return "SUCCESS"
}

function Eutester-LogHyperVQA{
    param ($source, $log)
       
    $logfile = "C:\hyperv_qa_log.txt"
    
    $now = [system.datetime]::now;
    [string]$msg = -join ("[$($source)]"," [$($now)] ", $log)
    add-content $logfile $msg
}


function Eutester-StartPXE
{
    param ([string[]]$IP, [string[]] $MAC)
    if($IP.Length -le 0)
    {    
        #set-content "C:\pxestat.txt" "ERROR: #ip is less than or equal 0"   
        #return "ERROR: #ip is less than or equal 0"
        LogHyperVQA "PXE" "ERROR: #ip is less than or equal 0"
        return "ERROR: #ip is less than or equal 0"
    }
    if($IP.Length -ne $MAC.Length){
        #set-content "C:\pxestat.txt" "ERROR: # of IPs and MACs are different"   
        LogHyperVQA "PXE" "ERROR: # of IPs and MACs are different"        
        return "ERROR: # of IPs and MACs are different";
    }    
    
    #$curstat = Get-Content "C:\pxestat.txt"
    #if($curstat -like "RUNNING")
    #{    
    #    return "ERROR: there's another pxe session running"
    #}
    foreach($hostname in $IP)
    {
        [string]$ret=get-content "C:\pxe_$($hostname).txt"
        if($ret -AND $ret.Contains("RUNNING"))
        {
            LogHyperVQA "PXE" "ERROR: $($hostname)'s PXE session is running now"
            return "ERROR: $($hostname)'s PXE session is running now";
        }
    }
        
    $proc = New-Object system.diagnostics.process;
    $proc.startinfo.FileName = "powershell.exe"
    [string]$ipArg =""
    foreach($i in $IP){
        $ipArg = -join ($ipArg, ",", $i)
    }
    $ipArg = $ipArg.Substring(1);
    [string]$macArg=""
    foreach($m in $MAC){
        $m = $m.replace(":","-");
        $macArg = -join ($macArg, ",", $m)
    }
    $macArg = $macArg.Substring(1);
    
    $proc.startinfo.Arguments ="-file C:\Users\Administrator\Documents\WindowsPowerShell\RunPXE.ps1 -ip $($ipArg) -mac $($macArg)"    
    $proc.StartInfo.UseShellExecute = $false
    $proc.StartInfo.RedirectStandardOutput = $true
    $proc.StartInfo.RedirectStandardError = $true
    
    LogHyperVQA "PXE" "args: $($proc.startinfo.Arguments)"    
    $proc.Start()
    
    
    LogHyperVQA "PXE" "PXE session started"    
    return "SUCCESS"
}


function Eutester-SetupHyperV{
    param ([string[]]$ip)
    
    if($ip -eq $null -OR $ip.Length -le 0){
        return "ERROR: no ip is given"
    }
    LogHypervQA $ip "SetupHyperV called"  
    foreach ($hostname in $ip)
    {
        $proc = New-Object system.diagnostics.process;
        $proc.startinfo.FileName = "powershell.exe"
        
        $proc.startinfo.Arguments ="-file C:\Users\Administrator\Documents\WindowsPowerShell\SetupHyperV.ps1 -ip $($hostname)"
        $proc.StartInfo.UseShellExecute = $false
        $proc.StartInfo.RedirectStandardOutput = $true
        $proc.StartInfo.RedirectStandardError = $true
        
        start-sleep -seconds 1
        $proc.Start()        
    }
        
    return "SUCCESS"
}


function Eutester-InstallEucalyptus{
    param ([string[]]$ip)
    
    if($ip -eq $null -OR $ip.Length -le 0){
        return "ERROR: no ip is given"
    }
    LogHyperVQA $ip "InstallEucalyptus called"
    $sleep = 0;
    foreach ($hostname in $ip)
    {
        $proc = New-Object system.diagnostics.process;
        $proc.startinfo.FileName = "powershell.exe"
        
        $proc.startinfo.Arguments ="-file C:\Users\Administrator\Documents\WindowsPowerShell\InstallPackages.ps1 -ip $($hostname) -sleep $($sleep)"
        $proc.StartInfo.UseShellExecute = $false
        $proc.StartInfo.RedirectStandardOutput = $true
        $proc.StartInfo.RedirectStandardError = $true
        
        $proc.Start()        
        $sleep += 20;
    }
        
    return "SUCCESS"
}

function Eutester-GetEucaInstallStatus
{
    param ([string[]]$ip)
    
    if($ip -eq $null -OR $ip.Length -le 0){
        LogHyperVQA $ip "GetEucaInstallStatus => ERROR: no ip is given"
        return "ERROR: no ip is given"
    }
    [int] $numSuccess=0;
    foreach($hostname in $ip)
    {
        $outfile = "C:\euca_install_$($hostname).txt"        
        if(![system.io.file]::Exists($outfile))
        {
            LogHyperVQA $ip "GetEucaInstallStatus => ERROR: file $($outfile) not found"
            return "ERROR: file $($outfile) not found"
        }
        
        $status = get-content $outfile
        if($status -like "SUCCESS")
        {
            $numSuccess++;
        }elseif($status -like "RUNNING")
        {
            continue;
        }else{
            LogHyperVQA $ip "GetEucaInstallStatus => ERROR: $($hostname) - $($status)"
            return "ERROR: $($hostname) - $($status)"
        }        
    }
    if($numSuccess -eq $ip.Length){
        LogHyperVQA $ip "GetEucaInstallStatus => SUCCESS"    
        return "SUCCESS";
    }else{
        LogHyperVQA $ip "GetEucaInstallStatus => RUNNING"    
        return "RUNNING";
    }
}

function Eutester-GetHyperVSetupStatus
{
    param ([string[]]$ip)
    
    if($ip -eq $null -OR $ip.Length -le 0)
    {
        LogHyperVQA $ip "GetHypervSetupStatus => ERROR: no ip is given"
        return "ERROR: no ip is given"
    }
    [int] $numSuccess=0;
    foreach($hostname in $ip)
    {
        $outfile = "C:\hyperv_setup_$($hostname).txt"
        if(![system.io.file]::Exists($outfile))
        {
            LogHyperVQA $ip "GetHypervSetupStatus => ERROR: file $($outfile) not found"
            return "ERROR: file $($outfile) not found"
        }
        
        $status = get-content $outfile
        if($status -like "SUCCESS")
        {
            $numSuccess++;
        }elseif($status -like "RUNNING")
        {
            continue;
        }else{
            LogHyperVQA $ip "GetHypervSetupStatus => ERROR: $($hostname) - $($status)"
            return "ERROR: $($hostname) - $($status)"
        }        
    }
    if($numSuccess -eq $ip.Length){
        LogHyperVQA $ip "GetHypervSetupStatus => SUCCESS"
        return "SUCCESS";
    }else{
        LogHyperVQA $ip "GetHypervSetupStatus => RUNNING"
        return "RUNNING";
    }
}


# {SUCCESS, RUNNING, ERROR: msg}
function Eutester-GetPXEStatus
{
    param ([string] $ip)
    
    try{
        if([system.io.File]::Exists("C:\pxe_$($ip).txt"))
        {
            [string]$ret=get-content "C:\pxe_$($ip).txt"
            if($ret -eq $null){
                return "ERROR: PXE info for $($ip) not found"
            }else{
                LogHyperVQA "$ip" "GetPXEStatus ==> $ret"
                return $ret;
            }
        }else{
            return "ERROR: PXE info for $($ip) not found"
        }
    }catch{
        return "ERROR: PXE info for $($ip) not found"
    }      
}


### FUNCTIONS RELATED TO WINDOWS QA ###
function Eutester-LogWinQA{
    param ($source, $log)
  
    #$logfile = "C:\win_qa_log.txt"
    $now = [system.datetime]::now;
    #[string]$msg = -join ("[$($source)]"," [$($now)] ", $log)
    write-debug "LogWinQA:$now:$msg"
    #add-content $logfile $msg
}

<#
    Hostname should match regex: "euca-[0-9A-Za-z]{5,}"
#>

function Eutester-Test-Euca-Hostname
{
    param ($session=$null, $hostname=$null)
    write-debug "Eutester-Test-Euca-Hostname starting, hostname:$hostname ..."
    $retry = 5;    
    LogWinQA $hostname "Testing hostname"
    while($retry-- -ge 0)
    {
        $ret = Test-Euca-Hostname-Impl -session $session -hostname $hostname
        if($ret -eq "SUCCESS")
        {
            write-debug "Testing hostname success"
            LogWinQA $hostname "Testing hostname: Sucess"
            exit 0
        }else{
            write-debug "Test hostname func returned: $ret, retries left $retry"
            LogWinQA $hostname "Testing hostname: $ret"
            Start-Sleep -seconds 3
        }
    }   
    exit 1 #error returns
}

function Eutester-Test-Euca-Hostname-Impl{
    param ($session=$null, $hostname=$null)
    
    if(!$session){ 
        if(!$EUCA_SESSION) { 
            write-debug "Eucalyptus testing session does not exist"
            return "Eucalyptus testing session not exist" 
        }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){
            return "RM Session could not be created"
        }
        if(!($session.State -eq "Opened")) { 
            return "RM Session is not open state"
        }    
    }
    
    $name = invoke-command -session $session -scriptblock {hostname}
    write-debug "Got name: $name"
    
    if($hostname -ne $NULL){ # there's hostname assigned by euca
        if($name -match $hostname) {
            write-debug "$name matches $hostname, success" 
            return "SUCCESS" 
        }else{ 
            #throw [system.management.automation.runtimeexception]"
            write-debug "$name doesnt match $hostname, error"
            return "Wrong hostname ($name)"
        }               
    }else{      
        # hostname not assigned, so random hostname has been generated
        if($name -match "euca-[0-9A-Za-z]{5,}"){
            write-debug "$name has euca- prefix assuming success"    
            return "SUCCESS"       
        }else{ 
            write-debug "$name does not have euca- prefix"
            #throw [system.management.automation.runtimeexception]        
            return "Wrong hostname ($name)"
        }     
   }
}

<#
    return domain name if the instance is part of a domain
    return null otherwise    
#>
function Eutester-Test-Euca-ADMembership{
    param ($session=$null)         
    write-debug('Eutester-Test-Euca-ADMembership starting')
    if(!$session){ 
        if(!$EUCA_SESSION) {
            write-debug('Eucalyptus testing session does not exist') 
            return "Eucalyptus testing session not exist" 
        }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){
            write-debug('RM Session could not be created')
            return "RM Session could not be created"
        }
        if(!($session.State -eq "Opened")) { 
            write-debug('RM Session is not open state')
            return "RM Session is not open state"
        }    
    }
    write-debug('Attempting AD membership...')
    LogWinQA $hostname "Testing AD membership"
    $wmiObj = invoke-command -session $session -scriptblock { get-wmiobject -query "select * from win32_computersystem"}
    if(!($wmiObj.PartOfDomain)) { 
        LogWinQA $hostname "Testing AD membership: Fail"
        write-debug("$hostname Testing AD membership not PartofDomain: Fail")
        exit 1 
    }
    else{                      
        LogWinQA $hostname "Testing AD membership: Success"
        write-debug("$hostname Testing AD membership: Success")
        $wmiObj.Domain
    }
}


function Eutester-Test-Euca-RDPermission
{
    param ($session=$null)      
    $retry = 5;
    LogWinQA $hostname "Testing RD permission"
    write-debug("$hostname Testing RD permission")     
    while($retry-- -ge 0)
    {
        $ret = Test-Euca-RDPermission-Impl -session $session
        if($ret -eq "SUCCESS")
        {
            LogWinQA $hostname "Testing RD permission: Success"
            write-debug("$hostname Testing RD permission: Success")
            return $ret
        }else{
            LogWinQA $hostname "Testing RD permission: $ret"
            write-debug("$hostname Testing RD permission: $ret")
            Start-Sleep -seconds 3
        }
    }   
    write-debug("Test-Euca-RDPermission-Impl failed: $ret")
    #return $ret
    exit 1 #error returns
}

function Eutester-Test-Euca-RDPermission-Impl{
   param ($session=$null)         
   write-debug('Eutester-Test-Euca-RDPermission-Impl starting...')
    if(!$session){ 
        if(!$EUCA_SESSION) { return "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){
            return "RM Session could not be created"
            #write-debug('RM Session could not be created')
            
        }
        if(!($session.State -eq "Opened")) { 
            return "RM Session is not open state"
            #write-debug('RM Session is not open state')
            
        }    
    }
    
    # test remote desktop Permission to designated AD users/groups
    write-debug('Testing remote desktop permissions to designated AD users and groups...')
    $users = invoke-command -session $session -scriptblock {net localgroup "Remote Desktop Users"}
    write-debug("Users: $users")
    if($users -notcontains "Administrator"){
        write-debug('Administrator is not allowed remote desktop permission, returning success')
        $msg = "Administrator is not allowed remote desktop permission"
        #return $msg --> https://support.eucalyptus.com/Ticket/Display.html?id=5497
        return "SUCCESS"
    }        
    if($users -notcontains "EUCAHOST-23-9\Domain Users" -and $users -notcontains "eucahost-23-9\Domain Users")
    {
        if($users -notcontains "EUCAHOST-23-10\Domain Users" -and $users -notcontains "eucahost-23-10\Domain Users")
        {
            $msg = "Domain Users are not allowed remote desktop permission"
            write-debug("$msg  returning success")
            # return $msg --> https://support.eucalyptus.com/Ticket/Display.html?id=5377
            return "SUCCESS"
        }
    }
    return "SUCCESS"
}

function Eutester-Test-Euca-ADKey
{
    param ($session=$null)
    $retry = 5;    
    write-debug("$hostname Eutester-Test-Euca-ADKey starting...")
    LogWinQA $hostname "Testing AD Credential vulenariblity"
    while($retry-- -ge 0)
    {        
        $ret = Test-Euca-ADKey-Impl -session $session
        if($ret -eq "SUCCESS")
        {
            write-debug("$hostname Testing AD Credential vulenariblity: Success")
            LogWinQA $hostname "Testing AD Credential vulenariblity: Success"
            return $ret
        }else{
            write-debug("$hostname Testing AD Credential vulenariblity retries remaining $retry , ret: $ret")
            LogWinQA $hostname "Testing AD Credential vulenariblity: $ret"
            Start-Sleep -seconds 3
        }
    }   
    write-debug("Eutester-Test-Euca-ADKey returning: $ret")
    exit 1
    #return $ret #error returns
}

function Eutester-Test-Euca-ADKey-Impl
{
    param ($session=$null)
    write-debug("Eutester-Test-Euca-ADKey-Impl...")
    if(!$session){ 
        if(!$EUCA_SESSION) { throw "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){throw "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { throw "RM Session is not open state"}    
    }
    
    $eucareg = invoke-command -session $session -scriptblock{get-itemproperty "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" "ADUsername"}
    if($eucareg){ 
        return "AD Username is found!"
    }else{
        write-debug('AD Username not found - good')
    }
    $eucareg = invoke-command -session $session -scriptblock{get-itemproperty "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" "ADPassword"}
    if($eucareg){ 
        return "AD Password is found!"
    }else{
        write-debug('AD Password not found - good')
    }
  
    return "SUCCESS"     
}
<#
   sequences:
    1) make sure there's scsi / nic devices named virtio
    2) write to C:\tmp
    3) ping google
#>
function Eutester-Test-Euca-VirtIO
{
    param ($session=$null)
    write-debug "Eutester-Test-Euca-VirtIO starting..."
    $retry = 5;    
    LogWinQA $hostname "Testing VirtIO"
    while($retry-- -ge 0)
    {
        $ret = Test-Euca-VirtIO-Impl -session $session
        if($ret -eq "SUCCESS")
        {
            write-debug "Test Virtio returned success"
            LogWinQA $hostname "Testing VirtIO: Success"
            exit 0
        }else{
            write-debug "Got return value: $ret , $retry retries left"
            LogWinQA $hostname "Testing VirtIO: $ret"
            Start-Sleep -seconds 3
        }
    }   
    exit 1 #error returns
}

function Eutester-Test-Euca-VirtIO-Impl{
    param ($session=$null)
    write-debug "Eutester-Test-VirtIO-Impl starting..."
    if(!$session){ 
        if(!$EUCA_SESSION) { return "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){return "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { return "RM Session is not open state"}    
    }
    
    write-debug "Got session, testing virtio..."  
    $objscsi = invoke-command -session $session -scriptblock { get-wmiobject -query "select * from win32_scsicontroller"}
    if(!($objscsi)){  throw "Can't query scsi controller using wmi" }
    $found=$false
    foreach($s in $objscsi){
        [string]$driver = $s.Name
        if($driver.ToLower().Contains("virtio")){  $found=$true; break }
    }
    if(!($found)){ return "Virtio SCSI driver is  not found"}
    $found=$false
    $objnic = invoke-command -session $session -scriptblock {get-wmiobject -query "select * from win32_networkadapter"}
    foreach($nic in $objnic){
        [string]$driver = $nic.Name
        if($driver.ToLower().Contains("virtio")){ $found=$true; break;}
    }    
    if(!($found)){return "Virtio NIC driver is not found"}
    
    # test file io
    invoke-command -session $session -scriptblock {set-content "C:\tmp.txt" "garbage"}
    $content = invoke-command -session $session -scriptblock {get-content "c:\tmp.txt"}
    if(!($content) -or $content -ne "garbage") { return "can't read/write a file"}
    
    # test network io
    $pingOk = $false
    $ping = invoke-command -session $session -scriptblock {ping -n 3 google.com}
    foreach($s in $ping) { if ($s.contains("Reply")){ $pingOk=$true; break}}    
    if(!($pingOk)){return "can't ping using the nic"}
    
    return "SUCCESS"
}


function Eutester-Test-Euca-XenPV
{
    param ($session=$null)
    write-debug "Eutester-Test-Euca-XenPV starting..."
    $retry = 5;    
    LogWinQA $hostname "Testing XenPV"
    while($retry-- -ge 0)
    {
        $ret = Test-Euca-XenPV-Impl -session $session
        if($ret -eq "SUCCESS")
        {
            write-debug "XenPV test returned success"
            LogWinQA $hostname "Testing XenPV: Success"
            exit 0
        }else{
            "XenPV test returned: $ret , $retry retries remaining"
            LogWinQA $hostname "Testing XenPV: $ret"
            Start-Sleep -seconds 3
        }
    }   
    exit 1 #error returns
}

function Eutester-Test-Euca-XenPV-Impl{
  param ($session=$null)
    write-debug "Eutester-Test-Euca-XenPV-Impl starting..."
    if(!$session){ 
        if(!$EUCA_SESSION) { return "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){return "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { return "RM Session is not open state"}    
    }
    
    write-debug "Session found testing xenpv..."
    $objscsi = invoke-command -session $session -scriptblock { get-wmiobject -query "select * from win32_scsicontroller"}
    if(!($objscsi)){  return "Can't query scsi controller using wmi" }
    $found=$false
    foreach($s in $objscsi){
        [string]$driver = $s.Name
        if($driver.ToLower().Contains("xen")){  $found=$true; break }
    }
    if(!($found)){ return "XenPV scsi driver is  not found"}
    $found=$false
    $objnic = invoke-command -session $session -scriptblock {get-wmiobject -query "select * from win32_networkadapter"}
    foreach($nic in $objnic){
        [string]$driver = $nic.Name
        if($driver.ToLower().Contains("xen")){ $found=$true; break;}
    }    
    if(!($found)){return "XenPV net driver is not found"}
    
    # test file io
    invoke-command -session $session -scriptblock {set-content "C:\tmp.txt" "garbage"}
    $content = invoke-command -session $session -scriptblock {get-content "c:\tmp.txt"}
    if(!($content) -or $content -ne "garbage") { return "can't read/write a file"}
    
    # test network io
    $pingOk = $false
    $ping = invoke-command -session $session -scriptblock {ping -n 3 google.com}
    foreach($s in $ping) { if ($s.contains("Reply")){ $pingOk=$true; break}}    
    if(!($pingOk)){return "can't ping using the nic"}
    
    return "SUCCESS"   
}

<#
diskpart.exe /s "script"

in the script:
select disk 1
[attribute disk clear readonly] # shouldn't be done for XP/server2003; script will terminate here }
online [disk] noerr # for win7/s2008, disk should be specified
clean
create partition primary
assign letter=G
exit

Now format:
echo Y | echo Y format G:/ /q /v:Data /fs:ntfs

[string]$dpartCmdS2003 = "`"select disk 1`", `"online noerr`", `"clean`", `"create partition primary`", `"assign letter=G`", `"exit`""
[string]$dpartCmdS2008 = "`"select disk 1`", `"attribute disk clear readonly`", `"online disk noerr`", `"clean`", `"create partition primary`", `"assign letter=G`", `"exit`""
#>
function Eutester-Test-Euca-EBS
{
    param ($session=$null, $diskno=1)
    write-debug "Eutester-Test-Euca-EBS starting diskno: $diskno"
    $retry = 5;    
    LogWinQA $hostname "Testing EBS"
    while($retry-- -ge 0)
    {
        $ret = Test-Euca-EBS-Impl -session $session -diskno $diskno
        if($ret -eq "SUCCESS")
        {
            write-debug "Test-Euca-EBS-Impl returned success"
            LogWinQA $hostname "Testing EBS: Success"
            exit 0
        }else{
            write-debug "Test-Euca-Ebs-Impl returned: $ret , $retry retries remaining"
            LogWinQA $hostname "Testing EBS: $ret"
            Start-Sleep -seconds 3
        }
    }   
    exit 1 #error returns
}

function Eutester-Test-Euca-EBS-Impl
{
    param ($session=$null, $diskno=1)
    write-debug "Eutester-Test-Euca-Ebs-Impl starting...."
    if(!$session){ 
        if(!$EUCA_SESSION) { return "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){return "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { return "RM Session is not open state"}    
    }
    
    
    $dletter = "F", "G", "H", "I", "J", "K", "L", "M", "N", "O"
    write-debug "Got session, using drive: $($dletter[$diskno])"
    $os = Get-Euca-OS -session $session    
    write-debug "OS=$os"
    if(($os -eq "VISTA") -or ($os -eq "WIN7") -or ($os -eq "S2008R2") -or ($os -eq "S2008")) 
    {
        invoke-command -session $session -args $($diskno+1), $($dletter[$diskno]) -scriptblock {param ($disk, $letter) set-content dpart.txt "select disk $disk", "attribute disk clear readonly", "online disk noerr", "clean", "create partition primary", "assign letter=$letter", "exit"}
    }elseif (($os -eq "XP") -or ($os -eq "S2003R2") -or ($os -eq "S2003"))
    {
        invoke-command -session $session -args $($diskno+1), $($dletter[$diskno]) -scriptblock {param ($disk, $letter) set-content dpart.txt "select disk $disk", "online noerr", "clean", "create partition primary", "assign letter=$letter", "exit"}
    }else
    { 
        Write-Warning "OS version can't be checked"
        invoke-command -session $session -args $($diskno+1), $($dletter[$diskno]) -scriptblock {param ($disk, $letter) set-content dpart.txt "select disk $disk", "online noerr", "clean", "create partition primary", "assign letter=$letter", "exit"}
    }     
    [string]$dpart = invoke-command -session $session -scriptblock {diskpart.exe /s dpart.txt}
    if(!($dpart.Contains("successfully assigned the drive letter")))
    { return "Disk part failed: $dpart"  }
        
    [string]$format = invoke-command -session $session -args "$($dletter[$diskno]):" -scriptblock {param ($drive) echo Y echo Y | format $drive /q /v:Data /fs:ntfs}
    if(!($format.Contains("Format complete"))) { return "Disk format failed: $format" }
    
    invoke-command -session $session -args "$($dletter[$diskno]):\tmp.txt" -scriptblock {param ($file) set-content $file "garbage"}
    $content = invoke-command -session $session -args "$($dletter[$diskno]):\tmp.txt" -scriptblock {param($file) get-content $file}
    if(!($content) -or $content -ne "garbage") { return "can't read/write a file"}
    return "SUCCESS"
}

function Eutester-Test-Euca-EphemeralDisk
{    
    param ($session=$null)
    write-debug "Eutester-Test-Euca-EphemeralDisk starting..."
    $retry = 5;    
    LogWinQA $hostname "Testing Ephemeral disks"
    while($retry-- -ge 0)
    {
        $ret = Test-Euca-EphemeralDisk-Impl -session $session
        if($ret -eq "SUCCESS")
        {
            write-debug "Testing Euca Ephemeral disk returned success"
            LogWinQA $hostname "Testing Ephemeral disks: Success"
            exit 0
        }else{
            write-debug "Testing Euca Ephemeral disk returned $ret , $retry retries remaining"
            LogWinQA $hostname "Testing Ephemeral disks: $ret"
            Start-Sleep -seconds 3
        }
    }   
    exit 1 #error returns
}

function Eutester-Test-Euca-EphemeralDisk-Impl
{
    param ($session=$null)
    if(!$session){ 
        if(!$EUCA_SESSION) { return "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){return "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { return "RM Session is not open state"}    
    }
    $drives = @("D:","E:")
    
    foreach ($drive in $drives){    
        $file = "$drive\tmp.txt";
        invoke-command -session $session -args $file -scriptblock {param ($file) set-content $file "garbage"}
        $content = invoke-command -session $session -args $file -scriptblock {param ($file) get-content $file}        
        if(!($content) -or $content -ne "garbage") 
            { continue; }
        else{
            return "SUCCESS"
        }
    }   
    return "Failed creating/reading files on ephemeral disks"    
}

function Eutester-Get-Euca-OS
{
    param ($session=$null)
    $retry = 5;    
    LogWinQA $hostname "Testing instance OS"
    while($retry-- -ge 0)
    {
        try{
            $ret = Get-Euca-OS-Impl -session $session
            LogWinQA $hostname "Testing instance OS: $ret"
            return $ret
        }catch{
            LogWinQA $hostname "Testing instance OS: Failed"
            Start-Sleep -seconds 3
        }
    }   
    return $ret #error returns
}

function Eutester-Get-Euca-OS-Impl
{
    param ($session=$null)
     if(!$session){ 
        if(!$EUCA_SESSION) { throw "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){throw "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { throw "RM Session is not open state"}    
    }    
    
    [string]$osName = invoke-command -session $session -scriptblock{$obj = get-wmiobject -query "Select * from win32_operatingsystem"; $obj.Name}
    
    if($osName.Contains("2003 R2")){return "S2003R2"}
    elseif($osName.Contains("2003")){return "S2003"}
    elseif($osName.Contains("XP")){return "XP"}
    elseif($osName.Contains("Vista")){return "VISTA"}
    elseif($osName.Contains("Windows 7") -or $osName.Contains("Windowsr 7")) {return "WIN7"}
    elseif($osName.Contains("2008 R2")){return "S2008R2"}
    elseif($osName.Contains("2008")){return "S2008"}
    else{throw "Unknown OS: $osName"}        
}


function Eutester-Get-Euca-InstallLocation
{
    param ($session=$null)
    $retry = 5;    
    LogWinQA $hostname "Testing Euca install location"
    while($retry-- -ge 0)
    {
        try{
            $ret = Get-Euca-InstallLocation-Impl -session $session
            LogWinQA $hostname "Testing Euca install location: $ret"
            return $ret
        }catch{
            LogWinQA $hostname "Testing Euca install location: Failed"
            Start-Sleep -seconds 3
        }
    }   
    return $ret #error returns
}

function Eutester-Get-Euca-InstallLocation-Impl{
    param ($session=$null)

    if(!$session){ 
        if(!$EUCA_SESSION) { throw "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){throw "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { throw "RM Session is not open state"}    
    }
    
    $eucareg = invoke-command -session $session -scriptblock{get-itemproperty "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" "InstallLocation"}
    if(!($eucareg)){ throw "Eucalyputus location is not found"}
    else{        
        return $eucareg.InstallLocation.Substring(0, $eucareg.InstallLocation.Length - 1)
     }
}

function Eutester-Add-Euca-Domain
{
    param ($session=$null)
    $retry = 5;    
    
    LogWinQA $hostname "Recording instance's domain attachment (S2003 domain)"    
    while($retry-- -ge 0)
    {
        $ret = Eutester-Eutester-Add-Euca-Domain-Impl-S2003 -session $session
        if($ret -eq "SUCCESS")
        {
            LogWinQA $hostname "Recording instance's domain attachment: Success"    
            return $ret
        }else{
            LogWinQA $hostname "Recording instance's domain attachment: $ret"    
            Start-Sleep -seconds 3
        }
    }   
    return $ret #error returns
}

function Eutester-Add-Euca-Domain-Impl { 
   param ($session=$null)
    if(!$session){ 
        if(!$EUCA_SESSION) { return "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){return "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { return "RM Session is not open state"}    
    }
    
    $eucaLoc =  Get-Euca-InstallLocation -session $session
    if(!($eucaLoc)) { return "Can't find the eucalyptus install location"}
    $exeFile = "$eucaLoc\euca.exe"
    write-debug $exeFile
    try{
        invoke-command -session $session -scriptblock { $key=[microsoft.win32.registry]::LocalMachine.OpenSubKey("SOFTWARE").OpenSubKey("Eucalyptus Systems").OpenSubKey("Eucalyptus", $true); $key.setvalue("ADUsername","Eucalyptus"); $key.setvalue("ADPassword","M00zm00z"); $key.Flush(); $key.Close(); }
    }catch{
        Write-Debug "x64 registry value is not written";
    }
    
    $ret = invoke-command -session $session -args $exeFile -scriptblock { param ($exe);&$exe "-setdom" "Eucalyptus" "M00zm00z" | out-string}
    
    if($ret -notmatch "SUCCESS"){  
        [string] $err = $ret;
        $err = $err.Trim();
        return "add domain info failed ($err)" 
    }
        
    return $ret;   
}

function Eutester-Eutester-Add-Euca-Domain-Impl-S2003 { 
   param ($session=$null)
    if(!$session){ 
        if(!$EUCA_SESSION) { return "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){return "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { return "RM Session is not open state"}    
    }
    
    $eucaLoc =  Get-Euca-InstallLocation -session $session
    if(!($eucaLoc)) { return "Can't find the eucalyptus install location"}
    $exeFile = "$eucaLoc\euca.exe"
    write-debug $exeFile
    try{
        invoke-command -session $session -scriptblock { $key=[microsoft.win32.registry]::LocalMachine.OpenSubKey("SOFTWARE").OpenSubKey("Eucalyptus Systems").OpenSubKey("Eucalyptus", $true); $key.setvalue("ADAddress", "eucahost-23-10.eucalyptus"); $key.setvalue("ADUsername","Eucalyptus"); $key.setvalue("ADPassword","M00zm00z"); $key.setvalue("ADOU","OU=Instances,OU=Eucalyptus,DC=eucahost-23-10,DC=eucalyptus"); $key.Flush(); $key.Close(); }
        invoke-command -session $session -scriptblock { $key=[microsoft.win32.registry]::LocalMachine.OpenSubKey("SOFTWARE").OpenSubKey("Eucalyptus Systems").OpenSubKey("Eucalyptus").OpenSubKey("RDP", $true); $key.setvalue("eucahost-23-10.eucalyptus\Domain Users", ""); $key.Flush(); $key.Close(); }
    }catch{
        Write-Debug "x64 registry value is not written";
    }
    
    $ret = invoke-command -session $session -args $exeFile -scriptblock { param ($exe);&$exe "-setdom" "Eucalyptus" "M00zm00z" | out-string}
    
    if($ret -notmatch "SUCCESS"){  
        [string] $err = $ret;
        $err = $err.Trim();
        return "add domain info failed ($err)" 
    }
        
    return $ret;   
}


function Eutester-Get-Euca-InstallVersion
{
    param ($session=$null)
    $retry = 5;    
    LogWinQA $hostname "Testing Euca install version"
    while($retry-- -ge 0)
    {
        try{
            $ret = Get-Euca-InstallVersion-Impl -session $session
            LogWinQA $hostname "Testing Euca install version: $ret"
            return $ret
        }catch{
            LogWinQA $hostname "Testing Euca install version: Failed"
            Start-Sleep -seconds 3
        }
    }   
    return $ret #error returns
}

function Eutester-Get-Euca-InstallVersion-Impl
{  
    param ($session=$null)
    if(!$session){ 
        if(!$EUCA_SESSION) { throw "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){throw "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { throw "RM Session is not open state"}    
    }
    
    $eucaLoc =  Get-Euca-InstallLocation -session $session
    if(!($eucaLoc)) { throw "Can't find the eucalyptus install location"}
    $dllFile="$eucaLoc\EucaService.dll"
    write-debug $dllFile
    [string]$version = invoke-command -session $session -args $dllFile -scriptblock {param ($dllLoc); [system.reflection.assemblyname]::GetAssemblyName("$dllLoc").Version}    
    if($version -eq $null){    throw "Unknown error occured" }
    else{ 
        return $version    
    }   
}


function Eutester-Get-Euca-Log
{
    param ($session=$null, $kind="all")
    $retry = 5;    
    LogWinQA $hostname "Retrieving euca log"
    while($retry-- -ge 0)
    {
        try{
            $ret = Get-Euca-Log-Impl -session $session -kind $kind
            LogWinQA $hostname "Retrieving euca log: Success"
            return $ret
        }catch{
            LogWinQA $hostname "Retrieving euca log: Fail"
            Start-Sleep -seconds 3
        }
    }   
    return $ret #error returns
}

function Eutester-Get-Euca-Log-Impl
{
    param ($session=$null, $kind="all")
    if(!$session){ 
        if(!$EUCA_SESSION) { throw "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){throw "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { throw "RM Session is not open state"}    
    }
     
    $logfile=$null
    if($kind -eq "main"){ $logfile = "eucalog.txt"}
    elseif($kind -eq "service") {$logfile = "eucalog_service.txt"}
    elseif($kind -eq "all"){}
    else{ throw "unknown kind specified"}
    
    $eucaLoc =  Get-Euca-InstallLocation -session $session
    if(!($eucaLoc)) { throw "Can't find the eucalyptus install location"}
    if($kind -eq "all"){        
      #  $logLocation = "$eucaLoc\eucalog_install.txt"
         [System.Text.StringBuilder] $log = new-object -typename system.text.stringbuilder 5000
      #  $log.Append("--------- eucalog_install.txt -----------") | out-null;$log.AppendLine() | out-null
      #  $tmp = invoke-command -session $session -args $logLocation -scriptblock { param ($logfile); get-content $logfile}
      #  foreach($s in $tmp){
      #       $log.Append($s) | out-null; $log.AppendLine() | out-null
      #  }
        $logLocation = "$eucaLoc\eucalog_service.txt"
        $log.Append("--------- eucalog_service.txt -----------") | out-null;$log.AppendLine() | out-null
        $tmp = invoke-command -session $session -args $logLocation -scriptblock { param ($logfile); get-content $logfile}
        foreach($s in $tmp){
             $log.Append($s) | out-null; $log.AppendLine() | out-null
        }
         $logLocation = "$eucaLoc\eucalog.txt"
        $log.Append("--------- eucalog.txt -----------") | out-null;$log.AppendLine() | out-null
        $tmp = invoke-command -session $session -args $logLocation -scriptblock { param ($logfile); get-content $logfile}
         foreach($s in $tmp){
             $log.Append($s) | out-null; $log.AppendLine() | out-null
        }        
        return $log.ToString()
    }else{
        $logLocation = "$eucaLoc\$logfile"
        $log = invoke-command -session $session -args $logLocation -scriptblock { param ($logfile); get-content $logfile}
    }
    if($log -eq $null) { throw "No log contents are found"}
    else{
        if($logout){set-content $logout $log}           
        else {  write-output $log }
    }   
}


#DEPRECATED: new instance automatically detached from AD
function Eutester-Remove-Euca-Domain
{
    param ($session=$null)
    $retry = 5;
    LogWinQA $hostname "Detaching instance from domain"    
    while($retry-- -ge 0)
    {
        $ret = Remove-Euca-Domain-Impl -session $session
        if($ret -eq "SUCCESS")
        {
            LogWinQA $hostname "Detaching instance from domain: Success"    
            return $ret
        }else{
            LogWinQA $hostname "Detaching instance from domain: $ret"    
            Start-Sleep -seconds 3
        }
    }   
    return $ret #error returns
}

function Eutester-Remove-Euca-Domain-Impl{
    param ($session=$null)
    if(!$session){ 
        if(!$EUCA_SESSION) { return "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){return "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { return "RM Session is not open state"}    
    }
       
    $eucaLoc =  Get-Euca-InstallLocation -session $session
    if(!($eucaLoc)) { return "Can't find the eucalyptus install location"}
    $exeFile = "$eucaLoc\euca.exe"
    write-debug $exeFile
    $unjoin = invoke-command -session $session -args $exeFile -scriptblock {param ($exe); &$exe "-unjoindom" | out-string}
    <#
        the string comparison operator (-eq, -contains, -like, -match) are picky. 
        only '-match' will correctly find a string match from win32 console outputs
    #>
    if($unjoin -notmatch "SUCCESS"){  
        [string] $err = $unjoin
        $err = $err.Trim();
    return "Unjoin domain failed ($err)" 
    }
    
    remove-pssession $session # because the same session can't be used after the machine leaves the domain
    write-debug "The RM session can't be established until the instance reboot"
    
    return "SUCCESS"    
}

# DEPRECATED: new instance will always be detached from AD
function Eutester-Remove-Euca-ADRecord
{
    param ($session=$null)
    LogWinQA $hostname "Removing AD record from instance"
    $retry = 5;    
    while($retry-- -ge 0)
    {
        $ret = Remove-Euca-ADRecord-Impl -session $session
        if($ret -eq "SUCCESS")
        {
            LogWinQA $hostname "Removing AD record from instance: Success"
            return $ret
        }else{
            LogWinQA $hostname "Removing AD record from instance: Fail"
            Start-Sleep -seconds 3
        }
    }   
    return $ret #error returns
}

function Eutester-Remove-Euca-ADRecord-Impl{
    param ($session=$null)
    if(!$session){ 
        if(!$EUCA_SESSION) { throw "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){throw "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { throw "RM Session is not open state"}    
    }
     $ret = invoke-command -session $session -scriptblock{
     try{
        remove-itemproperty -path "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" -name "ADAddress"; 
        remove-itemproperty -path "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" -name "ADUsername"; remove-itemproperty -path "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" -name "ADPassword";
        remove-itemproperty -path "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" -name "ADOU"
        }catch{
            return $error[0].Exception.Message
        }
        return "SUCCESS"
     }
     return $ret
}


# DEPRECATED
function Eutester-Remove-Euca-DomainAndRecord
{
    param ($session=$null)
    $retry = 5;    
    while($retry-- -ge 0)
    {
        $ret = Remove-Euca-DomainAndRecord-Impl -session $session
        if($ret -eq "SUCCESS")
        {
            return $ret
        }else{
            Start-Sleep -seconds 3
        }
    }   
    return $ret #error returns
}

# DEPRECATED
function Eutester-Remove-Euca-DomainAndRecord-Impl{
    param ($session=$null)
    if(!$session){ 
        if(!$EUCA_SESSION) { return "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){return "RM Session could not be created"}
        if(!($session.State -eq "Opened")) { return "RM Session is not open state"}    
    }
       
    $eucaLoc =  Get-Euca-InstallLocation -session $session
    if(!($eucaLoc)) { return "Can't find the eucalyptus install location"}
    $exeFile = "$eucaLoc\euca.exe"
    write-debug $exeFile
    $unjoin = invoke-command -session $session -args $exeFile -scriptblock { param ($exe); $ret = &$exe "-unjoindom" | out-string;
        if($ret -match "SUCCESS")
        {
            try{
                remove-itemproperty -path "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" -name "ADAddress"; 
                remove-itemproperty -path "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" -name "ADUsername"; remove-itemproperty -path "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" -name "ADPassword";
                remove-itemproperty -path "hklm:\SOFTWARE\Eucalyptus Systems\Eucalyptus" -name "ADOU"
               }catch{   return "Could not remove ad record: $error[0].Exception.Message"   }
            return "SUCCESS"
        }else{  return "Could not unjoin the domain: $ret" }
    }
        <#
            the string comparison operator (-eq, -contains, -like, -match) are picky. 
            only '-match' will correctly find a string match from win32 console outputs
        #>
    if($unjoin -notmatch "SUCCESS")
    {  
        [string] $err = $unjoin
        $err = $err.Trim();
        return "Unjoin domain failed ($err)" 
    }
    
    remove-pssession $session # because the same session can't be used after the machine leaves the domain
    write-debug "The RM session can't be established until the instance reboot"
    
    return "SUCCESS"    
}

# use nmap on the proxy machine (assume nmap for windows is installed)
# nmap -A {hostname} -p 3389 -PN
# DEPRECATED
function Eutester-Test-Euca-RDP
{
    param ($session=$null)
    if(!$session){ 
        if(!$EUCA_SESSION) { return "Eucalyptus testing session not exist" }
        $session = Get-RmSession $EUCA_HOSTNAME $EUCA_USERNAME $EUCA_PASSWORD
        if(!$session){return "RM Session could not be created"}
    }
    $nmap = "C:\Program Files (x86)\Nmap\nmap.exe"
   
    $repeat=3
    $i=0
    while ($i -lt $repeat) { 
        $i++      
        if(($session) -and ($session.State -eq "Opened")){
            $hostname = $session.ComputerName
            [string]$netstat = &$nmap -A $hostname -p 3389 -PN
            $idx = $netstat.IndexOf("3389/tcp")
            if($idx -lt 0){ $msg="host is not reachable using nmap"   }
            else{
                $status = $netstat.substring($netstat.IndexOf("3389/tcp")+8, 5).Trim()
                if($status -eq "open"){                     
                    return "SUCCESS"                
                }
                else{$msg="Port status=$status" }
            }
        }else
        {
            if(!($session)){$msg= "Session is null"}
            else{ $msg= "Session is not opened"}
        }
        sleep 1
    }
    
    throw $msg
}
#ver 03/16/11 - AD record update now directs S2003 domain (bundle-instance test will test Euca against s2003 Ad)
#ver 03/15/11 - Logging for win instance QA
#ver 01/28/11 - Eutester-Add-Euca-Domain-Impl to account for x64 registry setting
#ver 01/27/11 - Retry 5 times for each vm test functions
#ver 01/14/11 - HyperV deploy support
#ver 07/05/11 - Some fixes wrt 3.0
#ver 07/15/11 - added ephmeral disk test and modified EBS test
#ver 08/10/11 - added EBS scalability test support
#ver 12/05/11 - make tests more stable
