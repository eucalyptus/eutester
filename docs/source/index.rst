.. Eutester documentation master file, created by
   sphinx-quickstart on Sat Oct 13 15:19:01 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Eutester's documentation!
====================================

.. note::
    For API reference click here: :ref:`modindex` 

Eutester is designed to allow a user to quickly generate automated tests for testing a Eucalyptus or Amazon cloud. In the case of testing a private cloud a configuration file can be used to create cases that require root access to the machines. The config file describes a few things about the clouds configuration including the bare metal machine configuration and IPs.

Installation
----------------
If easy_install is not available in your environment use your package manager to install python-setuptools:
::
    yum install python-setuptools gcc python-devel  
    apt-get install python-setuptools gcc python-dev  
Installing eutester and its dependencies is as easy as
::
    easy_install eutester  
For development purposes you can then clone the code from github and then reinstall with your changes
::
    git clone https://github.com/eucalyptus/eutester.git  
    cd eutester  
    [CHANGE CODE]  
    python setup.py install  

Constructor
----------------
The basic constructor can be used for 2 different connections.

Private cloud with root access - CLC SSH, Cloud, and Walrus connections 
Purpose - connect to and manipulate Eucalyptus components using boto and command line. Recommended to use Eucaops. 
Required arguments: root password, config file with topology information 
Optional arguments: credential path so that new credentials are not created::
     private_cloud = Eucaops( password="my_root_pass",  config_file="cloud.conf")
     private_cloud.sys("euca-describe-availability-zones") ### use local credentials to determine viable availability-zones

Public cloud - local SSH, EC2 and S3 connections 
Purpose - can be used to wrap euca2ools commands installed locally on the tester machine or with Eucaops 
Required arguments: credential path::

     public_cloud = Eucaops(credpath="~/.eucarc")    
     public_cloud.run_instance(image) ## run an m1.small instance using image


Config file example
----------------
    clc.mydomain.com CENTOS 5.7 64 REPO [CC00 CLC SC00 WS]    
    nc1.mydomain.com VMWARE ESX-4.0 64 REPO [NC00] 

.. toctree::
   :maxdepth: 2



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

