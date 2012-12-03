Place holder for windows proxy tests and environment. Please add to this as 
tests are added, or env to run the tests change. 

TEST ENV:
In summary, the windowsproxytests eutester class wraps ssh commands to a remote windows server (running cygwin in this case). 
The ssh commands execute powershell methods from eutester_profile.ps1 which attempts to test windows guests. 

[eutester] ---ssh---> [windows_power_shell] ---remote power shell session---> [windows_guest_instance]

Tests:

