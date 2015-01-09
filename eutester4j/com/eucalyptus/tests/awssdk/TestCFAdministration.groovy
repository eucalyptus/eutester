package com.eucalyptus.tests.awssdk

import com.amazonaws.Request
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.handlers.AbstractRequestHandler
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.cloudformation.AmazonCloudFormationClient
import com.amazonaws.services.cloudformation.model.CreateStackRequest
import com.amazonaws.services.cloudformation.model.DeleteStackRequest
import com.amazonaws.services.cloudformation.model.DescribeStackEventsRequest
import com.amazonaws.services.cloudformation.model.DescribeStackResourcesRequest
import com.amazonaws.services.cloudformation.model.DescribeStacksRequest
import com.amazonaws.services.cloudformation.model.ListStackResourcesRequest
import com.amazonaws.services.cloudformation.model.ListStacksRequest
import com.amazonaws.services.identitymanagement.model.CreateAccessKeyRequest
import com.amazonaws.services.identitymanagement.model.CreateUserRequest
import com.amazonaws.services.identitymanagement.model.PutUserPolicyRequest
import com.amazonaws.services.simpleworkflow.model.DomainDeprecatedException
import com.amazonaws.services.simpleworkflow.model.TypeDeprecatedException
import com.github.sjones4.youcan.youare.YouAre
import com.github.sjones4.youcan.youare.model.CreateAccountRequest
import com.github.sjones4.youcan.youare.model.DeleteAccountRequest
import com.github.sjones4.youcan.youare.YouAreClient


import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;

/**
 * This application tests administration for CF resources.
 *
 * This is verification for the issue:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-10215
 */
class TestCFAdministration {

  private final String host;
  private final AWSCredentialsProvider credentials;

  public static void main( String[] args ) throws Exception {
    new TestCFAdministration( ).CFAdministrationTest( )
  }

  public TestCFAdministration( ) {
    minimalInit()
    this.host = HOST_IP
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
            .resolve( servicePath )
            .toString()
  }

  private YouAreClient getYouAreClient( final AWSCredentialsProvider credentials  ) {
    final YouAreClient euare = new YouAreClient( credentials )
    euare.setEndpoint( cloudUri( "/services/Euare" ) )
    euare
  }

  private AmazonCloudFormationClient getCloudFormationClient( final AWSCredentialsProvider credentials  ) {
    final AmazonCloudFormationClient cf = new AmazonCloudFormationClient( credentials )
    cf.setEndpoint( cloudUri( "/services/CloudFormation" ) )
    cf
  }

  private boolean assertThat( boolean condition,
                              String message ){
    assert condition : message
    true
  }

  private void print( String text ) {
    System.out.println( text )
  }

  @Test
  public void CFAdministrationTest( ) throws Exception {

    final String namePrefix = UUID.randomUUID().toString() + "-"
    print( "Using resource prefix for test: ${namePrefix}" )

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      final String userName = "${namePrefix}cf-test-user"
      AWSCredentialsProvider cfAccountCredentials = null
      AWSCredentialsProvider cfUserCredentials = null
      final YouAre youAre = getYouAreClient( credentials )
      youAre.with {
        final String accountName = "${namePrefix}cf-test-account"
        print( "Creating account for administration / IAM testing: ${accountName}" )
        String adminAccountNumber = createAccount( new CreateAccountRequest( accountName: accountName ) ).with {
          account?.accountId
        }
        assertThat( adminAccountNumber != null, "Expected account number" )
        print( "Created admin account with number: ${adminAccountNumber}" )
        cleanupTasks.add {
          print( "Deleting admin account: ${accountName}" )
          deleteAccount( new DeleteAccountRequest( accountName: accountName, recursive: true ) )
        }

        YouAre adminIam = getYouAreClient( credentials )
        adminIam.addRequestHandler( new AbstractRequestHandler(){
          public void beforeRequest(final Request<?> request) {
            request.addParameter( "DelegateAccount", accountName )
          }
        } )
        adminIam.with {
          print( "Creating access key for admin account: ${accountName}" )
          cfAccountCredentials = createAccessKey( new CreateAccessKeyRequest( userName: 'admin' ) ).with {
            accessKey?.with {
              new StaticCredentialsProvider( new BasicAWSCredentials( accessKeyId, secretAccessKey ) )
            }
          }

          assertThat( cfAccountCredentials != null, "Expected admin credentials" )
          print( "Created cf account access key: ${cfAccountCredentials.credentials.AWSAccessKeyId}" )

          print( "Creating user in admin account for policy testing: ${userName}" )
          final String userId = createUser( new CreateUserRequest( userName: userName, path: '/' ) ).with {
            user.userId
          }
          assertThat( userId != null, "Expected user ID" )
          print( "Created admin user with number: ${userId}" )

          print( "Creating access key for admin user: ${userName}" )
          cfUserCredentials = createAccessKey( new CreateAccessKeyRequest( userName: userName ) ).with {
            accessKey?.with {
              new StaticCredentialsProvider( new BasicAWSCredentials( accessKeyId, secretAccessKey ) )
            }
          }

          assertThat( cfUserCredentials != null, "Expected user credentials" )
          print( "Created cf user access key: ${cfAccountCredentials.credentials.AWSAccessKeyId}" )

          void
        }

        void
      }

      final String template = """\
            {
              "AWSTemplateFormatVersion" : "2010-09-09",
              "Description" : "Security group stack",
              "Resources" : {
                "SecurityGroup" : {
                 "Type" : "AWS::EC2::SecurityGroup",
                 "Properties" : {
                     "GroupDescription" : "Test security group"
                 }
                }
              }
            }
            """.stripIndent( ) as String

      final String stackName1 = "a-${namePrefix}stack"
      final String stackName2 = "b-${namePrefix}stack"
      String stackId1 = null
      String stackId2 = null
      getCloudFormationClient( cfAccountCredentials ).with {
        print( "Creating test stack: ${stackName1}" )
        stackId1 = createStack( new CreateStackRequest(
                stackName: stackName1,
                templateBody:template
        ) ).stackId
        assertThat( stackId1 != null, "Expected stack ID" )
        print( "Created stack with ID: ${stackId1}" )
        cleanupTasks.add{
          print( "Deleting stack: ${stackName1}" )
          deleteStack( new DeleteStackRequest( stackName: stackName1 ) )
        }

        print( "Creating test stack: ${stackName2}" )
        stackId2 = createStack( new CreateStackRequest(
                stackName: stackName2,
                templateBody:template
        ) ).stackId
        assertThat( stackId2 != null, "Expected stack ID" )
        print( "Created stack with ID: ${stackId2}" )
        cleanupTasks.add{
          print( "Deleting stack: ${stackName2}" )
          deleteStack( new DeleteStackRequest( stackName: stackName2 ) )
        }

        print( "Waiting for stack ${stackId1} creation" )
        ( 1..25 ).find{
          sleep 5000
          print( "Waiting for stack ${stackId1} creation, waited ${it*5}s" )
          describeStacks( new DescribeStacksRequest(
                  stackName: stackId1
          ) ).with {
            stacks?.getAt( 0 )?.stackId == stackId1 && stacks?.getAt( 0 )?.stackStatus == 'CREATE_COMPLETE'
          }
        }

        print( "Waiting for stack ${stackId2} creation" )
        ( 1..25 ).find{
          sleep 5000
          print( "Waiting for stack ${stackId2} creation, waited ${it*5}s" )
          describeStacks( new DescribeStacksRequest(
                  stackName: stackId2
          ) ).with {
            stacks?.getAt( 0 )?.stackId == stackId2 && stacks?.getAt( 0 )?.stackStatus == 'CREATE_COMPLETE'
          }
        }
      }

      getYouAreClient( cfAccountCredentials ).with {
        print( "Creating policy with stack permissions" )
        putUserPolicy( new PutUserPolicyRequest(
                userName: userName,
                policyName: 'cf-policy',
                policyDocument: """\
              {
                "Statement": [
                  {
                    "Action": [
                      "cloudformation:*"
                    ],
                    "Effect": "Allow",
                    "Resource": "${stackId1}"
                  },
                  {
                    "Action": [
                      "ec2:*"
                    ],
                    "Effect": "Allow",
                    "Resource": "*"
                  }
                ]
              }
              """.stripIndent( ) as String
        ) )
      }

      getCloudFormationClient( credentials ).with {
        println( "Verifying cloud admin does not see other account stacks when describing by default" )
        int adminStackCount = describeStacks( ).with {
          assertThat(
                  stacks.findAll{ [ stackId1, stackId2 ].contains( it.stackId )  }.empty,
                  "Expected no stacks from other accounts" )
          stacks.size( )
        }

        println( "Verifying cloud admin does not see other account stacks when listing" )
        listStacks( new ListStacksRequest() ).with {
          assertThat(
                  stackSummaries.findAll{ [ stackId1, stackId2 ].contains( it.stackId )  }.empty,
                  "Expected no stacks from other accounts" )
        }

        println( "Verifying cloud admin sees other account stacks with verbose describe" )
        describeStacks( new DescribeStacksRequest( stackName: 'verbose' ) ).with {
          assertThat( stacks?.size() > adminStackCount, "Expected to see other account stacks" )
        }

        println( "Verifying cloud admin sees other account stack with explicit describe" )
        describeStacks( new DescribeStacksRequest( stackName: stackId1 ) ).with {
          assertThat( 1 == stacks?.size(), "Expected 1 stack" )
        }

        println( "Verifying cloud admin can describe stack events" )
        describeStackEvents( new DescribeStackEventsRequest(
                stackName: stackId1
        ) ).with {
          assertThat( !stackEvents?.empty, "Expected stack events" )
        }

        println( "Verifying cloud admin can describe stack resources" )
        describeStackResources( new DescribeStackResourcesRequest(
                stackName: stackId1
        ) ).with {
          assertThat( !stackResources?.empty, "Expected stack resources" )
        }
      }

      getCloudFormationClient( cfUserCredentials ).with {
        println( "Verifying user sees permitted stack when describing" )
        describeStacks( ).with {
          assertThat( 1 == stacks?.size(), "Expected 1 stack" )
        }

        println( "Verifying user sees permitted stack when describing by name" )
        describeStacks( new DescribeStacksRequest( stackName: stackName1 ) ).with {
          assertThat( 1 == stacks?.size(), "Expected 1 stack" )
        }

        println( "Verifying user sees permitted stack when listing" )
        listStacks( ).with {
          assertThat( 1 == stackSummaries?.size(), "Expected 1 stack" )
        }

        println( "Verifying user can describe stack events" )
        describeStackEvents( new DescribeStackEventsRequest(
                stackName: stackName1
        ) ).with {
          assertThat( !stackEvents?.empty, "Expected stack events" )
        }

        println( "Verifying user can describe stack resources" )
        describeStackResources( new DescribeStackResourcesRequest(
                stackName: stackName1
        ) ).with {
          assertThat( !stackResources?.empty, "Expected stack resources" )
        }

        println( "Verifying user can list stack resources" )
        listStackResources( new ListStackResourcesRequest(
                stackName: stackName1
        ) ).with {
          assertThat( !stackResourceSummaries?.empty, "Expected stack resources" )
        }

        println( "Verifying user can delete stack ${stackName1}" )
        deleteStack( new DeleteStackRequest( stackName: stackName1 ) )

        print( "Waiting for stack ${stackName1} deletion" )
        ( 1..25 ).find{
          sleep 5000
          print( "Waiting for stack ${stackName1} deletion, waited ${it*5}s" )
          describeStacks( new DescribeStacksRequest(
                  stackName: stackName1
          ) ).with {
            stacks?.empty || ( stacks?.getAt( 0 )?.stackName == stackName1 && stacks?.getAt( 0 )?.stackStatus == 'DELETE_COMPLETE' )
          }
        }

        print( "Verifying stack deleted ${stackName1}" )
        describeStacks( new DescribeStacksRequest( stackName: stackName1 ) ).with {
          assertThat( stacks?.empty || stacks?.getAt( 0 )?.stackStatus == 'DELETE_COMPLETE', "Expected stack ${stackName1} deleted" )
        }
      }

      getCloudFormationClient( credentials ).with {
        println( "Verifying cloud admin can delete other accounts stack" )
        deleteStack( new DeleteStackRequest( stackName: stackId2 ) )

        print( "Waiting for stack ${stackId2} deletion" )
        ( 1..25 ).find{
          sleep 5000
          print( "Waiting for stack ${stackId2} deletion, waited ${it*5}s" )
          describeStacks( new DescribeStacksRequest(
                  stackName: stackId2
          ) ).with {
            stacks?.empty || ( stacks?.getAt( 0 )?.stackId == stackId2 && stacks?.getAt( 0 )?.stackStatus == 'DELETE_COMPLETE' )
          }
        }

        print( "Verifying stack deleted ${stackId2}" )
        describeStacks( new DescribeStacksRequest( stackName: stackId2 ) ).with {
          assertThat( stacks?.empty || stacks?.getAt( 0 )?.stackStatus == 'DELETE_COMPLETE', "Expected stack ${stackId2} deleted" )
        }
      }

      print( "Test complete" )
    } finally {
      // Attempt to clean up anything we created
      cleanupTasks.reverseEach { Runnable cleanupTask ->
        try {
          cleanupTask.run()
        } catch ( DomainDeprecatedException e ) {
          print( e.message )
        } catch ( TypeDeprecatedException e ) {
          print( e.message )
        } catch ( Exception e ) {
          e.printStackTrace()
        }
      }
    }
  }
}
