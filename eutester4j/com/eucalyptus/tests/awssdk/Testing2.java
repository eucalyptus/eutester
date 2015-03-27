/*************************************************************************
 * Copyright 2009-2014 Eucalyptus Systems, Inc.
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

import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.AmazonEC2Client;
import com.amazonaws.services.ec2.model.CreateSecurityGroupRequest;
import com.amazonaws.services.ec2.model.DeleteSecurityGroupRequest;
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancing;
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancingClient;
import com.amazonaws.services.identitymanagement.model.NoSuchEntityException;

import java.net.URI;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

/**
 * This application tests getting an access token using STS and consuming EC2 with the creds.
 *
 * https://eucalyptus.atlassian.net/browse/EUCA-8502
 */
public class Testing2 {


    private final String host = "10.111.5.53";
    private final String accessKey="AKI2K7IZSY4RPEZDMQCZ";
    private final String secretKey="8f3XvHb0F7ZpRg0InJ7POn9PlIYBe61xASPLb8HR";

    public static void main( String[] args ) throws Exception {
        final Testing2 test = new Testing2();
        test.test();
    }


    private String cloudUri( String servicePath ) {
        return
                URI.create( "http://" + host + ":8773/" )
                        .resolve( servicePath )
                        .toString();
    }


    private AmazonEC2 getEc2Client() {
        AWSCredentials creds = new BasicAWSCredentials(accessKey, secretKey);
        final AmazonEC2 ec2 = new AmazonEC2Client(creds);
        ec2.setEndpoint( cloudUri( "/services/Eucalyptus" ) );
        return ec2;
    }

    private  AmazonElasticLoadBalancing getElbClient() {
        AWSCredentials creds = new BasicAWSCredentials(accessKey, secretKey);
        final AmazonElasticLoadBalancing elb = new AmazonElasticLoadBalancingClient(creds);
        elb.setEndpoint(cloudUri( "/services/LoadBalancing"));
        return elb;
    }

    private void assertThat( boolean condition,
                             String message ){
        assert condition : message;
    }

    private void print( String text ) {
        System.out.println( text );
    }

    public void test() throws Exception {

        // End discovery, start test
        final String namePrefix = UUID.randomUUID().toString() + "-";
        print( "Using resource prefix for test: " + namePrefix );

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Create a resource in the account
            final String groupName = namePrefix + "group1";
            print( "Creating security group in account: " + groupName );
            final AmazonEC2 ec2 = getEc2Client();
            ec2.createSecurityGroup(new CreateSecurityGroupRequest().withGroupName(groupName).withDescription(groupName));
            cleanupTasks.add(new Runnable() {
                public void run() {
                    print("Deleting security group: " + groupName);
                    ec2.deleteSecurityGroup(new DeleteSecurityGroupRequest().withGroupName(groupName));
                }
            });



            print( "Test complete" );
        } finally {
            // Attempt to clean up anything we created
            Collections.reverse( cleanupTasks );
            for ( final Runnable cleanupTask : cleanupTasks ) {
                try {
                    cleanupTask.run();
                } catch ( NoSuchEntityException e ) {
                    print( "Entity not found during cleanup." );
                } catch ( Exception e ) {
                    e.printStackTrace();
                }
            }
        }
    }
}
