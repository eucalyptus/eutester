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
import com.amazonaws.services.cloudformation.model.Output
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.DescribeSubnetsRequest
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
 * Test VPC (CF) resource attributes and subnet (EC2) attributes.
 *
 * Related JIRA issues:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-11762
 *   https://eucalyptus.atlassian.net/browse/EUCA-11765
 */
class TestCloudFormationVPCAttributes {
  private final String host;
  private final AWSCredentialsProvider credentials;

  static void main( String[] args ) throws Exception {
    new TestCloudFormationVPCAttributes( ).testCloudFormationVPCAttributes( )
  }

  TestCloudFormationVPCAttributes( ) {
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

  private boolean assertThat( boolean condition,
                              String message ){
    assert condition : message
    true
  }

  private void print( String text ) {
    System.out.println( text )
  }

  @Test
  void testCloudFormationVPCAttributes( ) throws Exception {
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
            "Description": "VPC stack with no instances covering vpc and subnet parameters and attributes",
            "Resources": {
                "VPC": {
                    "Type": "AWS::EC2::VPC",
                    "Properties": {
                        "CidrBlock": "10.0.0.0/16",
                        "InstanceTenancy": "default"
                    }
                },
                "InternetGateway": {
                    "Type": "AWS::EC2::InternetGateway"
                },
                "AttachInternetGateway": {
                    "Type": "AWS::EC2::VPCGatewayAttachment",
                    "Properties": {
                        "InternetGatewayId": {
                            "Ref": "InternetGateway"
                        },
                        "VpcId": {
                            "Ref": "VPC"
                        }
                    }
                },
                "Subnet": {
                    "Type": "AWS::EC2::Subnet",
                    "Properties": {
                        "CidrBlock": "10.0.0.0/24",
                        "MapPublicIpOnLaunch": "true",
                        "VpcId": {
                            "Ref": "VPC"
                        }
                    }
                },
                "NetworkAcl": {
                    "Type": "AWS::EC2::NetworkAcl",
                    "Properties": {
                        "VpcId": {
                            "Ref": "VPC"
                        }
                    }
                },
                "AssociateNetworkAcl": {
                    "Type": "AWS::EC2::SubnetNetworkAclAssociation",
                    "Properties": {
                        "NetworkAclId": {
                            "Ref": "NetworkAcl"
                        },
                        "SubnetId": {
                            "Ref": "Subnet"
                        }
                    }
                },
                "RouteTable": {
                    "Type": "AWS::EC2::RouteTable",
                    "Properties": {
                        "VpcId": {
                            "Ref": "VPC"
                        }
                    }
                },
                "AssociateRouteTable": {
                    "Type": "AWS::EC2::SubnetRouteTableAssociation",
                    "Properties": {
                        "RouteTableId": {
                            "Ref": "RouteTable"
                        },
                        "SubnetId": {
                            "Ref": "Subnet"
                        }
                    }
                },
                "Route": {
                    "Type": "AWS::EC2::Route",
                    "Properties": {
                        "DestinationCidrBlock": "0.0.0.0/0",
                        "GatewayId": {
                            "Ref": "InternetGateway"
                        },
                        "RouteTableId": {
                            "Ref": "RouteTable"
                        }
                    }
                },
                "SecurityGroup": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {
                        "GroupDescription": "VPC security group",
                        "VpcId": {
                            "Ref": "VPC"
                        }
                    }
                },
                "SecurityGroupEgress": {
                    "Type": "AWS::EC2::SecurityGroupEgress",
                    "Properties": {
                        "CidrIp": "0.0.0.0/0",
                        "FromPort": "0",
                        "ToPort": "65535",
                        "GroupId": {
                            "Ref": "SecurityGroup"
                        },
                        "IpProtocol": "-1"
                    }
                },
                "SecurityGroupIngress": {
                    "Type": "AWS::EC2::SecurityGroupIngress",
                    "Properties": {
                        "CidrIp": "0.0.0.0/0",
                        "FromPort": "22",
                        "ToPort": "22",
                        "GroupId": {
                            "Ref": "SecurityGroup"
                        },
                        "IpProtocol": "tcp"
                    }
                }
            },
            "Outputs": {
                "VPCCidrBlock": {
                    "Value": {
                        "Fn::GetAtt": [
                            "VPC",
                            "CidrBlock"
                        ]
                    }
                },
                "VPCDefaultNetworkAcl": {
                    "Value": {
                        "Fn::GetAtt": [
                            "VPC",
                            "DefaultNetworkAcl"
                        ]
                    }
                },
                "VPCDefaultSecurityGroup": {
                    "Value": {
                        "Fn::GetAtt": [
                            "VPC",
                            "DefaultSecurityGroup"
                        ]
                    }
                },
                "SubnetAvailabilityZone": {
                    "Value": {
                        "Fn::GetAtt": [
                            "Subnet",
                            "AvailabilityZone"
                        ]
                    }
                },
                "AssociateNetworkAclAssociationId": {
                    "Value": {
                        "Fn::GetAtt": [
                            "AssociateNetworkAcl",
                            "AssociationId"
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
            templateBody: template
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

        print( "Describing stack ${stackName} to check outputs" )
        describeStacks( new DescribeStacksRequest(
            stackName: stackId
        ) ).with {
          assertThat( stacks!=null && stacks.size()==1, "Expected stack" )
          stacks[0].with {
            assertThat( outputs!=null && outputs.size()==5, "Expected five outputs" )
            outputs.each { Output output ->
              print( "Output ${output.outputKey}=${output.outputValue}" )
              switch ( output.outputKey ) {
                case 'VPCCidrBlock':
                  assertThat( output.outputValue=='10.0.0.0/16', "Expected VPCCidrBlock=10.0.0.0/16, but was: ${output.outputValue}" )
                  break;
                case 'VPCDefaultNetworkAcl':
                  assertThat( output.outputValue?.startsWith('acl-'), "Unexpected VPCDefaultNetworkAcl: ${output.outputValue}" )
                  break;
                case 'VPCDefaultSecurityGroup':
                  assertThat( output.outputValue?.startsWith('sg-'), "Unexpected VPCDefaultSecurityGroup: ${output.outputValue}" )
                  break;
                case 'SubnetAvailabilityZone':
                  assertThat( !output.outputValue.isEmpty(), "Expected SubnetAvailabilityZone" )
                  break;
                case 'AssociateNetworkAclAssociationId':
                  assertThat( output.outputValue?.startsWith('aclassoc-'), "Unexpected AssociateNetworkAclAssociationId: ${output.outputValue}" )
                  break;
                default:
                  assertThat( false, "Unexpected output attribute: ${output.outputKey}")
              }
            }
          }
        }

        print( "Describing stack ${stackName} resource Subnet" )
        String subnetId = describeStackResource( new DescribeStackResourceRequest(
            stackName: stackId,
            logicalResourceId: 'Subnet'
        ) ).with {
          assertThat( stackResourceDetail!=null, "Expected stack resource detail for ${stackName}/Subnet" )
          stackResourceDetail.with {
            assertThat( physicalResourceId!=null, "Expected physical resource id for ${stackName}/Subnet" )
            physicalResourceId
          }
        }
        print( "Found subnet ${subnetId} for stack ${stackName}" )

        print( "Verifying subnet MapPublicIpOnLaunch attribute " )
        getEC2Client( cfCredentials ).with {
          describeSubnets( new DescribeSubnetsRequest( subnetIds: [ subnetId ] ) ).with {
            assertThat( subnets!=null && subnets.size()==1, "Expected subnet" )
            subnets[0].with {
              assertThat( mapPublicIpOnLaunch, "Expected mapPublicIpOnLaunch==true")
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
