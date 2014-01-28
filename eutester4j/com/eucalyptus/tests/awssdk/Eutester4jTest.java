/**
 * Software License Agreement (BSD License)
 *
 * Copyright (c) 2009-2013, Eucalyptus Systems, Inc.
 * All rights reserved.
 *
 * Redistribution and use of this software in source and binary forms, with or
 * without modification, are permitted provided that the following conditions
 * are met:
 *
 *   Redistributions of source code must retain the above
 *   copyright notice, this list of conditions and the
 *   following disclaimer.
 *
 *   Redistributions in binary form must reproduce the above
 *   copyright notice, this list of conditions and the
 *   following disclaimer in the documentation and/or other
 *   materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 * 
 * @author tony
 */

package com.eucalyptus.tests.awssdk;

import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.services.autoscaling.model.LaunchConfiguration;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.AmazonEC2Client;
import com.amazonaws.services.ec2.model.*;
import org.testng.AssertJUnit;
import org.testng.annotations.AfterClass;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * At this time eucarc path needs to be hard coded. 
 * emi/ami an available image to use for creating instances (Required)
 * To test AWS or Euca comment out the lines for the one you do not want to 
 * test ie. "//euca" lines and uncomment the one you do ie. the "//AWS" lines
 */
public class Eutester4jTest {

	private static String secGroupName = "TestGroup-" + eucaUUID();
	private static String secGroupDesc = "TestDesc-" + eucaUUID();
	private static String keyName = "TestKey-" + eucaUUID();
	private static ArrayList<String> securityGroups = new ArrayList<String>();

//	private static String emi = "emi-8A1144D2"; //euca an emi you have access to

	/**
	 * Called once, before the first test is run. Creates an ec2 connection.
     * 
	 * @throws java.lang.Exception
	 */
	@BeforeClass
	public void setUpBeforeClass() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
		
//		ec2Endpoint = "http://ec2.us-west-1.amazonaws.com"; //AWS
//		asEndpoint = "http://autoscaling.us-west-1.amazonaws.com"; //AWS

		createSecurityGroup(secGroupName, secGroupDesc);
		createKeyPair(keyName);
		securityGroups.add(secGroupName);
	}

	/**
     * Called after all the tests in a class
     *
	 * @throws java.lang.Exception
	 */
	@AfterClass
	public void tearDownAfterClass() throws Exception {
//		sleep(60); // give the system a chance to complete test actions
		deleteKeyPair(keyName);
		deleteSecurityGroup(secGroupName);
		ec2 = null;
		as=null;
	}

	/*
	 * Test that invalid access key prevents execution of ec2 commands. There should be an exception caught
	 * After the test, credentials are reset to values present before the test ran.
	 */
	@Test(enabled=true)
	public void testInvalidAccessKey() {
		AWSCredentials creds = new BasicAWSCredentials("badAccessKey",SECRET_KEY);
		AmazonEC2 ec2Conn = new AmazonEC2Client(creds);
		ec2Conn.setEndpoint(EC2_ENDPOINT);
		try {
			ec2Conn.describeAvailabilityZones();
		} catch (Exception e) {
			print("Got Expected Failure: " + e.getMessage());
			AssertJUnit.assertTrue(e.getMessage().length() > 0);
		} 
	}
	
	/*
	 * Test that invalid secret key prevents execution of ec2 commands. There should be an exception caught.
	 * After the test, credentials are reset to values present before the test ran
	 */
	@Test(enabled=true)
	public void testInvalidSecretKey() {
		AWSCredentials creds = new BasicAWSCredentials(ACCESS_KEY,"badSecretKey");
		AmazonEC2 ec2Conn = new AmazonEC2Client(creds);
		ec2Conn.setEndpoint(EC2_ENDPOINT);
		try {
			ec2Conn.describeAvailabilityZones();
		} catch (Exception e) {
			print("Got Expected Failure: " + e.getMessage());
			AssertJUnit.assertTrue(e.getMessage().length() > 0);
		} 
	}
	
	/*
	 * Test that valid credentials have a successful connection by verifying
	 * a simple ec2 command (describeAvalabilityZones) returns some zones
	 */
	@Test(enabled=true)
	public void testGoodCreds() {
		DescribeAvailabilityZonesResult availabilityZonesResult = ec2.describeAvailabilityZones();
		AssertJUnit.assertTrue(availabilityZonesResult.getAvailabilityZones().size() >= 1);
	}
	
	/**
	 * Test that security group can be created then deletes the group
	 */
	@Test(enabled=true)
	public void testCreateSecurityGroup() {
		String name = eucaUUID();
		String desc = eucaUUID();
		
		List<SecurityGroup> secGroups = describeSecurityGroups();
		int initialSize = secGroups.size();
	
		try {
			createSecurityGroup(name, desc);
			secGroups = describeSecurityGroups();
			AssertJUnit.assertTrue(secGroups.size() > initialSize);
		} catch (Exception e) {
			e.printStackTrace();
		} finally {
			deleteSecurityGroup(name);
		}
	}
	
	/**
	 * Test that security group can be deleted
	 */
	@Test(enabled=true)
	public void testDeleteSecurityGroup() {
		String name = eucaUUID();
		String desc = eucaUUID();
	
		try {
			createSecurityGroup(name, desc);
			
			List<SecurityGroup> secGroups = describeSecurityGroups();
			int initialSize = secGroups.size();
			
			deleteSecurityGroup(name);
			secGroups = describeSecurityGroups();
			AssertJUnit.assertTrue(secGroups.size() < initialSize);
		} catch (Exception e) {
			e.printStackTrace();
		}
	}
	
	/**
	 * Test running instances also tests get instance count
	 */
	@Test(enabled=false)
	public void testRunInstances(){
		int initalInstanceCount = getInstancesList().size();
		runInstances(IMAGE_ID, keyName, INSTANCE_TYPE, securityGroups, 1, 1);
		AssertJUnit.assertTrue(getInstancesList().size() > initalInstanceCount);
		
		// terminate after the test
		List<String> instanceIds = new ArrayList<String>();
		instanceIds.add(getLastlaunchedInstance().get(0).getInstanceId());
		print("Going to terminate " + getLastlaunchedInstance().get(0).getInstanceId());
		terminateInstances(instanceIds);
		print("Terminate requested");

	}
	
	/**
	 * test stopping instances (bfebs image required)
	 *
	 * appears there is a compatibility issue with euca supporting getState() for instances
	 * it is always returning null
	 */
	@Test(enabled=false)
	public void testStopInstances(){
		runInstances(IMAGE_ID, keyName, INSTANCE_TYPE, securityGroups, 1, 1);
		List<String> instanceIds = new ArrayList<String>();
		instanceIds.add(getLastlaunchedInstance().get(0).getInstanceId());
		
		String instance = getLastlaunchedInstance().get(0).getInstanceId();
		
		final DescribeInstanceStatusResult instanceStatusResult = ec2
				.describeInstanceStatus(new DescribeInstanceStatusRequest()
						.withInstanceIds(instance));
		
		final InstanceStatus status = instanceStatusResult
				.getInstanceStatuses().get(0);
		print("Status: " + status.getInstanceState().toString());
		while(!getLastlaunchedInstance().get(0).getState().getName().equals("running")){}
		stopInstances(instanceIds);
		while(!getLastlaunchedInstance().get(0).getState().getName().equals("stopped")){}
		AssertJUnit.assertTrue(getLastlaunchedInstance().get(0).getState().getName().equals("stopped"));
		// after test terminate the instance
		terminateInstances(instanceIds);
	}
	
	/**
	 * test terminating
	 * 
	 * appears there is a compatibility issue with euca supporting getState() for instances
	 * it is always returning null
	 */
	@Test(enabled=false)
	public void testTerminateInstances(){
		runInstances(IMAGE_ID, keyName, INSTANCE_TYPE, securityGroups, 1, 1);
		List<String> instanceIds = new ArrayList<String>();
		instanceIds.add(getLastlaunchedInstance().get(0).getInstanceId());
		print("Created instance = " + getLastlaunchedInstance().get(0).getInstanceId());
		print("State: " + getLastlaunchedInstance().get(0).getState());
		print("State before terminate = " + getLastlaunchedInstance().get(0).getState().getName());
		terminateInstances(instanceIds);
		print("State after terminate = " + getLastlaunchedInstance().get(0).getState().getName());
		while(!getLastlaunchedInstance().get(0).getState().getName().equals("terminated")){}
		AssertJUnit.assertTrue(getLastlaunchedInstance().get(0).getState().getName().equals("terminated"));
	}
	
	/**
	 * Tests createKeyPair, getKeyPairCount and deleteKeyPair
	 */
	@Test(enabled=true)
	public void testCreateKeyPair() {
		String keyName = "test key";
		int initialKeyPairCount = getKeyPairCount();
		createKeyPair(keyName);
		AssertJUnit.assertTrue(getKeyPairCount() > initialKeyPairCount);
		deleteKeyPair(keyName);
	}
	
	/**
	 * Tests create, describe and delete launch configurations
	 */
	@Test(enabled=true)
	public void testBasicLaunchConfig(){
        String launchConfig = "LC-" + eucaUUID();
		try {
            createLaunchConfig(launchConfig,IMAGE_ID,INSTANCE_TYPE,null,null,null,null,null,null,null,null);
			List<LaunchConfiguration> launchConfigs = describeLaunchConfigs();
			int initialSize = launchConfigs.size();
			deleteLaunchConfig(launchConfig);
			launchConfigs = describeLaunchConfigs();
			AssertJUnit.assertTrue(launchConfigs.size() < initialSize);
		} catch (Exception e) {
			e.printStackTrace();
		}
	}
}
