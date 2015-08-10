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

import java.net.URI;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import com.amazonaws.Request;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.auth.BasicSessionCredentials;
import com.amazonaws.handlers.AbstractRequestHandler;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.AmazonEC2Client;
import com.amazonaws.services.ec2.model.CreateSecurityGroupRequest;
import com.amazonaws.services.ec2.model.DeleteSecurityGroupRequest;
import com.amazonaws.services.ec2.model.DescribeSecurityGroupsRequest;
import com.amazonaws.services.ec2.model.DescribeSecurityGroupsResult;
import com.amazonaws.services.identitymanagement.model.AccessKey;
import com.amazonaws.services.identitymanagement.model.CreateAccessKeyRequest;
import com.amazonaws.services.identitymanagement.model.CreateAccessKeyResult;
import com.amazonaws.services.identitymanagement.model.NoSuchEntityException;
import com.github.sjones4.youcan.youare.YouAreClient;
import com.github.sjones4.youcan.youare.model.CreateAccountRequest;
import com.github.sjones4.youcan.youare.model.DeleteAccountRequest;
import com.github.sjones4.youcan.youtoken.YouTokenClient;
import com.github.sjones4.youcan.youtoken.model.GetImpersonationTokenRequest;
import com.github.sjones4.youcan.youtoken.model.GetImpersonationTokenResult;
import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;
/**
 * This application tests getting an impersonation token using STS and consuming EC2 with the creds.
 *
 * https://eucalyptus.atlassian.net/browse/EUCA-8496
 */
public class TestSTSGetImpersonationToken {

  private final String host;
  private final String accessKey;
  private final String secretKey;

  public static void main( String[] args ) throws Exception {
    final TestSTSGetImpersonationToken test =  new TestSTSGetImpersonationToken();
    test.STSGetImpersonationTokenTest();
  }

  public TestSTSGetImpersonationToken() throws Exception{
    minimalInit();
    this.host = HOST_IP;
    this.accessKey = ACCESS_KEY;
    this.secretKey = SECRET_KEY;
  }

  private AWSCredentials credentials() {
    return new BasicAWSCredentials( accessKey, secretKey );
  }

  private String cloudUri( String servicePath ) {
    return
        URI.create( "http://" + host + ":8773/" )
            .resolve( servicePath )
            .toString();
  }

  private AmazonEC2 getEc2ClientUsingToken( final String accountAlias,
                                            final String userName ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( new AWSCredentialsProvider(){
      @Override
      public AWSCredentials getCredentials() {
        final YouTokenClient tokens = new YouTokenClient( credentials() );
        tokens.setEndpoint( cloudUri( "/services/Tokens" ) );
        final GetImpersonationTokenResult impersonationTokenResult = tokens.getImpersonationToken(
            new GetImpersonationTokenRequest()
                .withAccountAlias( accountAlias)
                .withUserName( userName )
        );

        return new BasicSessionCredentials(
            impersonationTokenResult.getCredentials().getAccessKeyId(),
            impersonationTokenResult.getCredentials().getSecretAccessKey(),
            impersonationTokenResult.getCredentials().getSessionToken()
        );
      }

      @Override
      public void refresh() {
      }
    } );
    ec2.setEndpoint( cloudUri( "/services/Eucalyptus" ) );
    return ec2;
  }

  private YouAreClient getYouAreClient( ) {
    final YouAreClient euare = new YouAreClient( credentials( ) );
    euare.setEndpoint( cloudUri( "/services/Euare" ) );
    return euare;
  }

  private YouAreClient getYouAreClient( final String asAccount ) {
    final YouAreClient euare = new YouAreClient( credentials( ) );
    euare.addRequestHandler( new AbstractRequestHandler(){
      public void beforeRequest(final Request<?> request) {
        request.addParameter( "DelegateAccount", asAccount );
      }
    } );
    euare.setEndpoint( cloudUri( "/services/Euare" ) );
    return euare;
  }

  private AmazonEC2 getEc2Client( final AccessKey accessKey ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( new BasicAWSCredentials(
        accessKey.getAccessKeyId(),
        accessKey.getSecretAccessKey() ) );
    ec2.setEndpoint( cloudUri( "/services/Eucalyptus" ) );
    return ec2;
  }

  private void assertThat( boolean condition,
                           String message ){
    assert condition : message;
  }

  private void print( String text ) {
    System.out.println( text );
  }

  @Test
  public void STSGetImpersonationTokenTest() throws Exception {
    final YouAreClient euare = getYouAreClient();

    // End discovery, start test
    final String namePrefix = UUID.randomUUID().toString() + "-";
    print( "Using resource prefix for test: " + namePrefix );

    final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
    try {
      // Create account to use for testing
      final String accountName = namePrefix + "admin-account1";
      print( "Creating admin account: " + accountName );
      String adminAccountNumber = euare.createAccount( new CreateAccountRequest( ).withAccountName( accountName ) )
          .getAccount().getAccountId();
      assertThat( adminAccountNumber != null, "Expected account number" );
      print( "Created admin account with number: " + adminAccountNumber );
      cleanupTasks.add( new Runnable() {
        public void run( ) {
          print( "Deleting admin account: " + accountName );
          euare.deleteAccount( new DeleteAccountRequest(  ).withAccountName( accountName ).withRecursive( true ) );
        }
      } );

      final YouAreClient euareDelegate = getYouAreClient( accountName );
      final CreateAccessKeyResult result = euareDelegate.createAccessKey( new CreateAccessKeyRequest().withUserName( "admin" ) );
      print( "Create access key for admin account: " + result.getAccessKey().getAccessKeyId() );

      // Create a resource in the account
      final String groupName = namePrefix + "group1";
      print( "Creating security group in account: " + groupName );
      final AmazonEC2 ec2 = getEc2Client( result.getAccessKey( ) );
      ec2.createSecurityGroup( new CreateSecurityGroupRequest( ).withGroupName( groupName ).withDescription( groupName ) );
      cleanupTasks.add( new Runnable() {
        public void run( ) {
          print( "Deleting security group: " + groupName );
          ec2.deleteSecurityGroup( new DeleteSecurityGroupRequest( ).withGroupName( groupName ) );
        }
      } );

      print( "Describing security groups via impersonation for admin@" + accountName );
      final AmazonEC2 ec2AsAccount = getEc2ClientUsingToken( accountName, "admin" );
      final DescribeSecurityGroupsResult describeSecurityGroupsResult =
          ec2AsAccount.describeSecurityGroups( new DescribeSecurityGroupsRequest().withGroupNames( groupName ) );
      print( describeSecurityGroupsResult.toString( ) );
      assertThat( 1 == describeSecurityGroupsResult.getSecurityGroups().size(), "Expected one security group" );
      assertThat( groupName.equals( describeSecurityGroupsResult.getSecurityGroups().get( 0 ).getGroupName() ), "Expected group name: " + groupName );

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
