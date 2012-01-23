eutester version 0.0.1
======================

eutester is an attempt to leverage existing test code to make test writing faster and standardized.

Design
------

Eutester is designed to allow a user to quickly generate automated tests for testing a Eucalyptus cloud. There is a configuration file
associated with the library that describes a few things about the clouds configuration including the bare metal machine configuration and IPs.


Constructor
------

The basic constructor can be used for a few different connections:

1. Instance - Only SSH connection
    Purpose - connect to instances in the cloud  
    Required arguments: private key path and hostname

        instance = Eutester( hostname=instance.ip_address, keypath="my_key.pem")
        instance.sys("mount") # check mount points on instance and return the output as a list
        
2. Private cloud with root access - CLC SSH, Cloud, and Walrus connections
    Purpose - connect to and manipulate Eucalyptus components using boto and command line. Recommended to use Eucaops.  
    Required arguments: root password, config file with topology information  
    Optional arguments: credential path so that new credentials are not created

        private_cloud = Eucaops( password="my_root_pass",  config_file="cloud.conf", credpath="~/.euca")
        
3. Public cloud - local SSH, EC2 and S3 connections
    Purpose - can be used to wrap euca2ools commands installed locally on the tester machine or with Eucaops  
    Required arguments: root password, config file with topology information

        
        local = Eucaops(credpath="~/.eucarc")   
        local.sys("euca-describe-availability-zones") ### use local credentials to determine viable availability-zones 
        local.run_instance(image) ## run an m1.small instance using image
            
 
Config file
----------

The configuration file for (2) private cloud mode has the following structure:

    clc.mydomain.com CENTOS 5.7 64 REPO [CC00 CLC SC00 WS]    
    nc1.mydomain.com VMWARE ESX-4.0 64 REPO [NC00]



Columns
------ 
    IP or hostname of machine  
    Distro installed on machine  
    Distro version on machine  
    Distro base architecture  
    List of components installed on this machine encapsulated in brackets []

These components can be:

    CLC - Cloud Controller   
    WS - Walrus   
    SC00 - Storage controller for cluster 00   
    CC00 - Cluster controller for cluster 00    
    NC00 - A node controller in cluster 00   