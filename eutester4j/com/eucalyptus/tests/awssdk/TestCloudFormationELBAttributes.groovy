package com.eucalyptus.tests.awssdk

import com.amazonaws.Request
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.handlers.AbstractRequestHandler
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.cloudformation.AmazonCloudFormationClient
import com.amazonaws.services.cloudformation.model.CreateStackRequest
import com.amazonaws.services.cloudformation.model.DeleteStackRequest
import com.amazonaws.services.cloudformation.model.DescribeStackResourceRequest
import com.amazonaws.services.cloudformation.model.DescribeStacksRequest
import com.amazonaws.services.cloudformation.model.Parameter
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.DescribeAvailabilityZonesResult
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancing
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancingClient
import com.amazonaws.services.elasticloadbalancing.model.DescribeLoadBalancerAttributesRequest
import com.amazonaws.services.identitymanagement.model.CreateAccessKeyRequest
import com.amazonaws.services.simpleworkflow.model.DomainDeprecatedException
import com.amazonaws.services.simpleworkflow.model.TypeDeprecatedException
import com.github.sjones4.youcan.youare.YouAre
import com.github.sjones4.youcan.youare.YouAreClient
import com.github.sjones4.youcan.youare.model.CreateAccountRequest
import com.github.sjones4.youcan.youare.model.DeleteAccountRequest
import org.testng.annotations.Test

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * Test CloudFormation LoadBalancer properties for connection settings and access logs.
 *
 * Related JIRA issues:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-11763
 *   https://eucalyptus.atlassian.net/browse/EUCA-11856
 */
class TestCloudFormationELBAttributes {
  private final String host;
  private final AWSCredentialsProvider credentials;

  static void main( String[] args ) throws Exception {
    new TestCloudFormationELBAttributes( ).testCloudFormationELBAttributes( )
  }

  TestCloudFormationELBAttributes( ) {
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

  private AmazonEC2 getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials )
    ec2.setEndpoint( cloudUri( "/services/compute" ) )
    ec2
  }


  private AmazonElasticLoadBalancing getELBClient( final AWSCredentialsProvider credentials ) {
    final AmazonElasticLoadBalancing elb = new AmazonElasticLoadBalancingClient( credentials )
    elb.setEndpoint( cloudUri( "/services/LoadBalancing" ) )
    elb
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
  void testCloudFormationELBAttributes( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    // Find an AZ to use
    final DescribeAvailabilityZonesResult azResult = ec2.describeAvailabilityZones();

    assertThat( azResult.getAvailabilityZones().size() > 0, "Availability zone not found" );

    final String availabilityZone = azResult.getAvailabilityZones().get( 0 ).getZoneName();
    print( "Using availability zone: " + availabilityZone );

    final String namePrefix = UUID.randomUUID().toString() + "-"
    print( "Using resource prefix for test: ${namePrefix}" )

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      AWSCredentialsProvider cfCredentials = null
      final YouAre youAre = getYouAreClient( credentials )
      youAre.with {
        final String accountName = "${namePrefix}cf-test-account"
        print( "Creating account for cloudformation testing: ${accountName}" )
        String adminAccountNumber = createAccount( new CreateAccountRequest( accountName: accountName ) ).with {
          account?.accountId
        }
        assertThat( adminAccountNumber != null, "Expected account number" )
        print( "Created admin account with number: ${adminAccountNumber}" )
        cleanupTasks.add {
          print( "Deleting test account: ${accountName}" )
          deleteAccount( new DeleteAccountRequest( accountName: accountName, recursive: true ) )
        }

        YouAre adminIam = getYouAreClient( credentials )
        adminIam.addRequestHandler( new AbstractRequestHandler(){
          public void beforeRequest(final Request<?> request) {
            request.addParameter( "DelegateAccount", accountName )
          }
        } )
        adminIam.with {
          print( "Creating access key for cloudformation test account: ${accountName}" )
          cfCredentials = createAccessKey( new CreateAccessKeyRequest( userName: 'admin' ) ).with {
            accessKey?.with {
              new StaticCredentialsProvider( new BasicAWSCredentials( accessKeyId, secretAccessKey ) )
            }
          }

          assertThat( cfCredentials != null, "Expected test credentials" )
          print( "Created cloudformation test access key: ${cfCredentials.credentials.AWSAccessKeyId}" )

          void
        }

        void
      }

      final String template = '''\
            {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Description": "Template testing ELB attributes",
                "Parameters": {
                    "Zone": {
                        "Description": "The zone to use",
                        "Type": "String",
                        "Default": "one"
                    }
                },
                "Resources": {
                    "Bucket": {
                        "Type": "AWS::S3::Bucket"
                    },
                    "LoadBalancer": {
                        "Type": "AWS::ElasticLoadBalancing::LoadBalancer",
                        "Properties": {
                            "AccessLoggingPolicy": {
                                "EmitInterval": "5",
                                "Enabled": "true",
                                "S3BucketName": {
                                    "Ref": "Bucket"
                                },
                                "S3BucketPrefix": "elb-access-log"
                            },
                            "AvailabilityZones": [
                                {
                                    "Ref": "Zone"
                                }
                            ],
                            "ConnectionSettings": {
                                "IdleTimeout": "15"
                            },
                            "CrossZone": "true",
                            "HealthCheck": {
                                "HealthyThreshold": "10",
                                "Interval": "30",
                                "Target": "HTTP:8000/",
                                "Timeout": "5",
                                "UnhealthyThreshold": "2"
                            },
                            "Listeners": [
                                {
                                    "InstancePort": "8000",
                                    "LoadBalancerPort": "8000",
                                    "Protocol": "HTTP",
                                    "InstanceProtocol": "HTTP"
                                }
                            ]
                        }
                    }
                }
            }
            '''.stripIndent( ) as String

      final String stackName = "cf-${namePrefix}stack"
      String stackId = null
      getCloudFormationClient( cfCredentials ).with {
        print( "Creating test stack: ${stackName}" )
        stackId = createStack( new CreateStackRequest(
            stackName: stackName,
            templateBody: template,
            parameters: [
              new Parameter( parameterKey: 'Zone', parameterValue: availabilityZone )
            ]
        ) ).stackId
        assertThat( stackId != null, "Expected stack ID" )
        print( "Created stack with ID: ${stackId}" )
        cleanupTasks.add{
          print( "Deleting stack: ${stackName}" )
          deleteStack( new DeleteStackRequest( stackName: stackName ) )
        }

        print( "Waiting for stack ${stackId} creation" )
        ( 1..25 ).find{
          sleep 5000
          print( "Waiting for stack ${stackId} creation, waited ${it*5}s" )
          describeStacks( new DescribeStacksRequest(
              stackName: stackId
          ) ).with {
            stacks?.getAt( 0 )?.stackId == stackId && stacks?.getAt( 0 )?.stackStatus == 'CREATE_COMPLETE'
          }
        }

        print( "Describing stack ${stackName} resource LoadBalancer" )
        String elbName = describeStackResource( new DescribeStackResourceRequest(
            stackName: stackId,
            logicalResourceId: 'LoadBalancer'
        ) ).with {
          assertThat( stackResourceDetail!=null, "Expected stack resource detail for ${stackName}/LoadBalancer" )
          stackResourceDetail.with {
            assertThat( physicalResourceId!=null, "Expected physical resource id for ${stackName}/LoadBalancer" )
            physicalResourceId
          }
        }

        print( "Describing stack ${stackName} resource Bucket" )
        String bucketName = describeStackResource( new DescribeStackResourceRequest(
            stackName: stackId,
            logicalResourceId: 'Bucket'
        ) ).with {
          assertThat( stackResourceDetail!=null, "Expected stack resource detail for ${stackName}/Bucket" )
          stackResourceDetail.with {
            assertThat( physicalResourceId!=null, "Expected physical resource id for ${stackName}/Bucket" )
            physicalResourceId
          }
        }

        print( "Found ELB for stack: ${elbName}, describing attributes" )
        getELBClient( cfCredentials ).with {
          describeLoadBalancerAttributes( new DescribeLoadBalancerAttributesRequest(
              loadBalancerName: elbName
          ) ).with {
            assertThat( loadBalancerAttributes!=null, "Expected attributes for load balancer ${elbName}" )
            loadBalancerAttributes.with {
              assertThat( accessLog!=null, "Expected accessLog attribute for load balancer ${elbName}" )
              assertThat( connectionSettings!=null, "Expected connectionSettings attribute for load balancer ${elbName}" )
              assertThat( crossZoneLoadBalancing!=null, "Expected crossZoneLoadBalancing attribute for load balancer ${elbName}" )
              print( "Verifying access logging attribute" )
              accessLog.with {
                assertThat( enabled, "Expected access logging enabled for ${elbName}" )
                assertThat( emitInterval==5, "Expected emitInterval=5 for ${elbName}, but was: ${emitInterval}" )
                assertThat( s3BucketName==bucketName, "Expected bucket name=${bucketName} for ${elbName}, but was: ${s3BucketName}" )
                assertThat( s3BucketPrefix=='elb-access-log', "Expected bucket prefix=elb-access-log for ${elbName}, but was: ${s3BucketPrefix}" )
              }
              print( "Verifying connection setting attribute" )
              connectionSettings.with {
                assertThat( idleTimeout==15, "Expected idle timeout=15 for ${elbName}, but was: ${idleTimeout}" )
              }
              print( "Verifying cross zone load balancing attribute" )
              crossZoneLoadBalancing.with {
                assertThat( enabled, "Expected cross zone balancing enabled for ${elbName}" )
              }
            }
          }
        }

        print( "Deleting stack ${stackName}" )
        deleteStack( new DeleteStackRequest( stackName: stackName ) )

        print( "Waiting for stack ${stackName} deletion" )
        ( 1..25 ).find{
          sleep 5000
          print( "Waiting for stack ${stackName} deletion, waited ${it*5}s" )
          describeStacks( new DescribeStacksRequest(
              stackName: stackName
          ) ).with {
            stacks?.empty || ( stacks?.getAt( 0 )?.stackName == stackName && stacks?.getAt( 0 )?.stackStatus == 'DELETE_COMPLETE' )
          }
        }

        print( "Verifying stack deleted ${stackName}" )
        describeStacks( new DescribeStacksRequest( stackName: stackName ) ).with {
          assertThat( stacks?.empty || stacks?.getAt( 0 )?.stackStatus == 'DELETE_COMPLETE', "Expected stack ${stackName} deleted" )
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
