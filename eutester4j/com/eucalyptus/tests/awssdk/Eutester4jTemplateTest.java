/*************************************************************************
 * Copyright 2009-2013 Eucalyptus Systems, Inc.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see http://www.gnu.org/licenses/.
 *
 * Please contact Eucalyptus Systems, Inc., 6755 Hollister Ave., Goleta
 * CA 93117, USA or visit http://www.eucalyptus.com/licenses/ if you need
 * additional information or have any questions.
 ************************************************************************/

package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

import java.util.ArrayList;
import java.util.List;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.model.DescribeKeyPairsRequest;
import com.amazonaws.services.ec2.model.DescribeKeyPairsResult;
import com.amazonaws.services.ec2.model.DescribeSecurityGroupsRequest;
import com.amazonaws.services.ec2.model.DescribeSecurityGroupsResult;

/**
 * 
 * Description: This class demonstrates simple usage of eutester4j library.
 * The test is run as a java application but the library can be used as 
 * part of tests written in any framework.
 * 
 * This test will get access and secret keys as well as urls and endpoints
 * for services of a eucalyptus cloud. (easily modifiable to point to AWS 
 * creds) The tests pefromed are create a security group, a keypair, find
 * an image and spin up an instance then terminate the instance and delete
 * the keypair and security group created.
 *
 * @author tony 
 */
public class Eutester4jTemplateTest {

	final String securityGroup = "SECURITY-GROUP-" + eucaUUID();
	final String keyName = "KEYPAIR-" + eucaUUID();

	/**
	 * @param args
	 */
	public static void main(String[] args) throws Exception {
		final Eutester4jTemplateTest test = new Eutester4jTemplateTest();
		test.test();
		test.cleanup();
		System.out.println("Test complete");
	}

	private void test() throws Exception {
		// get cloud endpoints and keys create connection and find images
		getCloudInfo();
		final AmazonEC2 ec2 = getEc2Client(ACCESS_KEY, SECRET_KEY, EC2_ENDPOINT);
		final String imageId = findImage(ec2);
		
		// create a security group
		createSecurityGoup(ec2, securityGroup, "A Test Security Group");
		DescribeSecurityGroupsRequest describeSecurityGroupsRequest = new DescribeSecurityGroupsRequest();
		DescribeSecurityGroupsResult securityGroupsResult = ec2
				.describeSecurityGroups(describeSecurityGroupsRequest);
		assertThat(securityGroupsResult.getSecurityGroups().size() > 0,
				"Security Group Not Created");

		// create a keypair
		createKeyPair(ec2, keyName);
		DescribeKeyPairsRequest describeKeyPairsRequest = new DescribeKeyPairsRequest();
		DescribeKeyPairsResult describeKeyPairsResult = ec2
				.describeKeyPairs(describeKeyPairsRequest);
		assertThat(describeKeyPairsResult.getKeyPairs().size() > 0,
				"Keypair not created");

		// Run an Instance
		int initalInstanceCount = getInstancesList(ec2).size();
		ArrayList<String> securityGroups = new ArrayList<String>();
		securityGroups.add(securityGroup);
		runInstances(ec2, imageId, keyName, instanceType, securityGroups, 0, 1);
		assertThat(getInstancesList(ec2).size() > initalInstanceCount, "Instance not launched");
	}

	public void cleanup() {
		// terminate the last launched instance
		final AmazonEC2 ec2 = getEc2Client(ACCESS_KEY, SECRET_KEY, EC2_ENDPOINT);
		List<String> instanceIds = new ArrayList<String>();
		instanceIds.add(getLastlaunchedInstance(ec2).get(0).getInstanceId());
		terminateInstances(ec2, instanceIds);
		
		// wait for the instance to be terminated before trying to delete group
		while(!getLastlaunchedInstance(ec2).get(0).getState().getName().equals("terminated")){}
		deleteKeyPair(ec2, keyName);
		deleteSecurityGroup(ec2, securityGroup);
	}
}