package com.eucalyptus.tests.awssdk

import com.amazonaws.Request
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.handlers.AbstractRequestHandler
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*
import com.amazonaws.services.identitymanagement.model.CreateAccessKeyRequest
import com.amazonaws.services.identitymanagement.model.CreateUserRequest
import com.amazonaws.services.identitymanagement.model.PutUserPolicyRequest
import com.github.sjones4.youcan.youare.YouAre
import com.github.sjones4.youcan.youare.YouAreClient
import com.github.sjones4.youcan.youare.model.CreateAccountRequest
import com.github.sjones4.youcan.youare.model.DeleteAccountRequest

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests IAM policy for EC2 VPC resource conditions.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9936
 */
class TestEC2VPCResourceConditionPolicy {

  private final String host
  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCResourceConditionPolicy( ).EC2VPCResourceConditionPolicyTest( )
  }

  public TestEC2VPCResourceConditionPolicy() {
    minimalInit()

    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
        .resolve( servicePath )
        .toString()
  }

  private AmazonEC2 getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials )
    ec2.setEndpoint( EC2_ENDPOINT )
    ec2
  }

  private YouAreClient getYouAreClient( final AWSCredentialsProvider credentials  ) {
    final YouAreClient euare = new YouAreClient( credentials )
    euare.setEndpoint( cloudUri( "/services/Euare/" ) )
    euare
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
  public void EC2VPCResourceConditionPolicyTest( ) throws Exception {
    final String namePrefix = UUID.randomUUID().toString() + "-"
    print( "Using resource prefix for test: ${namePrefix}" )

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      String vpcAccountNumber = null
      AWSCredentialsProvider vpcAccountCredentials = null
      AWSCredentialsProvider vpcPermCredentials = null
      AWSCredentialsProvider vpcDenyCredentials = null
      final String vpcRegion = ''
      final YouAre youAre = getYouAreClient( credentials )
      final String accountName = "${namePrefix}vpc-rescond-test"
      youAre.with {
        print( "Creating account for resource condition testing: ${accountName}" )
        vpcAccountNumber = createAccount( new CreateAccountRequest( accountName: accountName ) ).with {
          account?.accountId
        }
        assertThat( vpcAccountNumber != null, "Expected account number" )
        print( "Created admin account with number: ${vpcAccountNumber}" )
        cleanupTasks.add {
          print( "Deleting admin account: ${accountName}" )
          deleteAccount( new DeleteAccountRequest( accountName: accountName, recursive: true ) )
        }

        print( "Creating access key for vpc test account: ${accountName}" )
        YouAre adminIam = getYouAreClient( credentials )
        adminIam.addRequestHandler( new AbstractRequestHandler(){
          public void beforeRequest(final Request<?> request) {
            request.addParameter( "DelegateAccount", accountName )
          }
        } )
        vpcAccountCredentials = adminIam.with {
          createAccessKey( new CreateAccessKeyRequest( userName: "admin" ) ).with {
            accessKey?.with {
              new StaticCredentialsProvider( new BasicAWSCredentials( accessKeyId, secretAccessKey ) )
            }
          }
        }
        assertThat(vpcAccountCredentials != null, "Expected credentials")
        print("Created vpc account access key: ${vpcAccountCredentials.credentials.AWSAccessKeyId}")
      }

      print( "Creating 'permitted' test user in vpc account ${accountName}" )
      getYouAreClient( vpcAccountCredentials ).with {
        createUser( new CreateUserRequest(
          path: '/',
          userName: 'permitted'
        ) )

        vpcPermCredentials = createAccessKey( new CreateAccessKeyRequest( userName: 'permitted' ) ).with {
          accessKey?.with {
            new StaticCredentialsProvider( new BasicAWSCredentials( accessKeyId, secretAccessKey ) )
          }
        }
        assertThat( vpcPermCredentials != null, "Expected credentials" )
        print( "Created vpc user access key: ${vpcPermCredentials.credentials.AWSAccessKeyId}" )
        void
      }

      String imageId = null
      String keyName = null
      getEC2Client( vpcAccountCredentials ).with {
        // Find an image to use
        imageId = describeImages( new DescribeImagesRequest(
            filters: [
                new Filter( name: "image-type", values: ["machine"] ),
                new Filter( name: "root-device-type", values: ["instance-store"] ),
            ]
        ) ).with {
          images?.getAt( 0 )?.imageId
        }
        assertThat( imageId != null , "Image not found" )
        print( "Using image: ${imageId}" )

        // Discover SSH key
        keyName = describeKeyPairs().with {
          keyPairs?.getAt(0)?.keyName
        }
        print( "Using key pair: " + keyName );

      }

      print( "Creating 'denied' test user in vpc account ${accountName}" )
      getYouAreClient( vpcAccountCredentials ).with {
        createUser( new CreateUserRequest(
            path: '/',
            userName: 'denied'
        ) )

        vpcDenyCredentials = createAccessKey( new CreateAccessKeyRequest( userName: 'denied' ) ).with {
          accessKey?.with {
            new StaticCredentialsProvider( new BasicAWSCredentials( accessKeyId, secretAccessKey ) )
          }
        }
        assertThat( vpcDenyCredentials != null, "Expected credentials" )
        print( "Created vpc user access key: ${vpcDenyCredentials.credentials.AWSAccessKeyId}" )
        void
      }

      getEC2Client( vpcAccountCredentials ).with {
        print('Creating VPC')
        String vpcId = createVpc(new CreateVpcRequest(cidrBlock: '10.1.2.0/24')).with {
          vpc?.vpcId
        }
        print("Created VPC with id ${vpcId}")
        cleanupTasks.add {
          print("Deleting VPC ${vpcId}")
          deleteVpc(new DeleteVpcRequest(vpcId: vpcId))
        }

        print( 'Creating internet gateway' )
        final String internetGatewayId = createInternetGateway( new CreateInternetGatewayRequest( ) ).with {
          internetGateway?.internetGatewayId
        }
        print( "Created internet gateway ${internetGatewayId}" )
        cleanupTasks.add{
          print( "Deleting internet gateway ${internetGatewayId}" )
          deleteInternetGateway( new DeleteInternetGatewayRequest( internetGatewayId: internetGatewayId ) )
        }

        print( "Attaching internet gateway ${internetGatewayId} to vpc ${vpcId}" )
        attachInternetGateway( new AttachInternetGatewayRequest( internetGatewayId: internetGatewayId, vpcId: vpcId ) )
        cleanupTasks.add{
          print( "Detaching internet gateway ${internetGatewayId} from vpc ${vpcId}" )
          detachInternetGateway( new DetachInternetGatewayRequest( internetGatewayId: internetGatewayId, vpcId: vpcId ) )
        }

        print( "Creating subnet" )
        final String subnetId = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: '10.1.2.0/24' )).with {
          subnet?.subnetId
        }
        print( "Created subnet ${subnetId}" )
        cleanupTasks.add{
          print( "Deleting subnet ${subnetId}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId ) )
        }

        getYouAreClient( vpcAccountCredentials ).with {
          print( "Adding policy for allow user" )
          putUserPolicy( new PutUserPolicyRequest(
              userName: 'permitted',
              policyName: 'allow',
              policyDocument: """\
              {
                 "Statement": [
                  {
                    "Effect": "Allow",
                    "Action": [
                      "ec2:AuthorizeSecurityGroupEgress",
                      "ec2:AuthorizeSecurityGroupIngress",
                      "ec2:DeleteNetworkAcl",
                      "ec2:DeleteNetworkAclEntry",
                      "ec2:DeleteRoute",
                      "ec2:DeleteRouteTable",
                      "ec2:DeleteSecurityGroup",
                      "ec2:RevokeSecurityGroupEgress",
                      "ec2:RevokeSecurityGroupIngress"
                    ],
                    "Resource": "*",
                    "Condition": {
                       "ArnEquals": {
                          "ec2:Vpc": "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:vpc/${vpcId}"
                       }
                    }
                 },
                 {
                    "Effect": "Allow",
                    "Action": "ec2:RunInstances",
                    "Resource": [
                       "arn:aws:ec2:${vpcRegion}::vmtype/*",
                       "arn:aws:ec2:${vpcRegion}::availabilityzone/*",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:subnet/${subnetId}",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:network-interface/*",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:instance/*",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:volume/*",
                       "arn:aws:ec2:${vpcRegion}::image/*",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:key-pair/*",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:security-group/*"
                    ]
                 }
                 ]
              }
              """.stripIndent()
          ) )

          print( "Adding policy for deny user" )
          putUserPolicy( new PutUserPolicyRequest(
              userName: 'denied',
              policyName: 'deny',
              policyDocument: """\
              {
                 "Statement": [
                  {
                    "Effect": "Allow",
                    "Action": [
                      "ec2:AuthorizeSecurityGroupEgress",
                      "ec2:AuthorizeSecurityGroupIngress",
                      "ec2:DeleteNetworkAcl",
                      "ec2:DeleteNetworkAclEntry",
                      "ec2:DeleteRoute",
                      "ec2:DeleteRouteTable",
                      "ec2:DeleteSecurityGroup",
                      "ec2:RevokeSecurityGroupEgress",
                      "ec2:RevokeSecurityGroupIngress"
                    ],
                    "Resource": "*",
                    "Condition": {
                       "ArnEquals": {
                          "ec2:Vpc": "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:vpc/vpc-00000001"
                       }
                    }
                 },
                 {
                    "Effect": "Allow",
                    "Action": "ec2:RunInstances",
                    "Resource": [
                       "arn:aws:ec2:${vpcRegion}::vmtype/*",
                       "arn:aws:ec2:${vpcRegion}::availabilityzone/*",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:subnet/subnet-00000001",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:network-interface/*",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:instance/*",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:volume/*",
                       "arn:aws:ec2:${vpcRegion}::image/*",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:key-pair/*",
                       "arn:aws:ec2:${vpcRegion}:${vpcAccountNumber}:security-group/*"
                    ]
                 }
                 ]
              }
              """.stripIndent()
          ) )
        }

        final String securityGroupName = "${namePrefix}TestGroup1"
        print( "Creating security group ${securityGroupName} in vpc ${vpcId}" )
        final String groupId = createSecurityGroup( new CreateSecurityGroupRequest(
          groupName: securityGroupName,
          description: securityGroupName,
          vpcId: vpcId
        ) ).with {
          groupId
        }
        print( "Created security group ${securityGroupName} with identifier ${groupId}" )

        getEC2Client( vpcPermCredentials ).with {
          print( "Authorizing egress with allow user" )
          authorizeSecurityGroupEgress( new AuthorizeSecurityGroupEgressRequest(
              groupId: groupId,
              ipPermissions: [
                  new IpPermission(
                      ipProtocol: 2,
                      ipRanges: [ '10.0.0.0/8' ]
                  )
              ]
          ) )

          print( "Authorizing ingress with allow user" )
          authorizeSecurityGroupIngress( new AuthorizeSecurityGroupIngressRequest(
              groupId: groupId,
              ipPermissions: [
                  new IpPermission(
                      ipProtocol: 2,
                      ipRanges: [ '10.0.0.0/8' ]
                  )
              ]
          ) )
        }

        getEC2Client( vpcDenyCredentials ).with {
          print( "Authorizing egress with deny user" )
          try {
            authorizeSecurityGroupEgress( new AuthorizeSecurityGroupEgressRequest(
                groupId: groupId,
                ipPermissions: [
                    new IpPermission(
                        ipProtocol: 2,
                        ipRanges: [ '10.0.0.0/8' ]
                    )
                ]
            ) )
            assertThat( false, "Expected authorize egress failure for user without permission in vpc")
          } catch( Exception e ) {
            print( "Expected failure for authorize egress denied ${e}" )
          }

          print( "Authorizing ingress with deny user" )
          try {
            authorizeSecurityGroupIngress( new AuthorizeSecurityGroupIngressRequest(
                groupId: groupId,
                ipPermissions: [
                    new IpPermission(
                        ipProtocol: 2,
                        ipRanges: [ '10.0.0.0/8' ]
                    )
                ]
            ) )
            assertThat( false, "Expected authorize ingress failure for user without permission in vpc")
          } catch( Exception e ) {
            print( "Expected failure for authorize ingress denied ${e}" )
          }

          print( "Revoking egress with deny user" )
          try {
            revokeSecurityGroupEgress( new RevokeSecurityGroupEgressRequest(
                groupId: groupId,
                ipPermissions: [
                    new IpPermission(
                        ipProtocol: 2,
                        ipRanges: [ '10.0.0.0/8' ]
                    )
                ]
            ) )
            assertThat( false, "Expected revoke egress failure for user without permission in vpc")
          } catch( Exception e ) {
            print( "Expected failure for revoke egress denied ${e}" )
          }

          print( "Revoking ingress with deny user" )
          try {
            revokeSecurityGroupIngress( new RevokeSecurityGroupIngressRequest(
                groupId: groupId,
                ipPermissions: [
                    new IpPermission(
                        ipProtocol: 2,
                        ipRanges: [ '10.0.0.0/8' ]
                    )
                ]
            ) )
            assertThat( false, "Expected revoke ingress failure for user without permission in vpc")
          } catch( Exception e ) {
            print( "Expected failure for revoke ingress denied ${e}" )
          }

          void
        }

        getEC2Client( vpcPermCredentials ).with {
          print( "Revoking egress with allow user" )
          revokeSecurityGroupEgress( new RevokeSecurityGroupEgressRequest(
              groupId: groupId,
              ipPermissions: [
                  new IpPermission(
                      ipProtocol: 2,
                      ipRanges: [ '10.0.0.0/8' ]
                  )
              ]
          ) )

          print( "Revoking ingress with allow user" )
          revokeSecurityGroupIngress( new RevokeSecurityGroupIngressRequest(
              groupId: groupId,
              ipPermissions: [
                  new IpPermission(
                      ipProtocol: 2,
                      ipRanges: [ '10.0.0.0/8' ]
                  )
              ]
          ) )
        }

        print( "Deleting security group with deny user" )
        getEC2Client( vpcDenyCredentials ).with {
          try {
            deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: groupId ) )
            assertThat( false, "Expected delete failure for user without permission to delete security group resource in vpc")
          } catch( Exception e ) {
            print( "Expected failure for security group delete denied ${e}" )
          }

          void
        }

        print( "Deleting security group with allow user" )
        getEC2Client( vpcPermCredentials ).with {
          deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: groupId ) )
        }

        print( "Creating network acl in vpc ${vpcId}" )
        String networkAclId = createNetworkAcl( new CreateNetworkAclRequest( vpcId: vpcId ) ).with {
          networkAcl?.networkAclId
        }
        print( "Created network acl with id ${networkAclId}" )
        cleanupTasks.add{
          print( "Deleting network acl ${networkAclId}" )
          deleteNetworkAcl( new DeleteNetworkAclRequest( networkAclId: networkAclId ) )
        }

        print( "Creating network acl entry in ${networkAclId}" )
        createNetworkAclEntry( new CreateNetworkAclEntryRequest(
            networkAclId: networkAclId,
            ruleNumber: 200,
            ruleAction: 'allow',
            egress: false,
            cidrBlock: '0.0.0.0/0',
            protocol: -1
        ) )

        getEC2Client( vpcDenyCredentials ).with {
          print( "Deleting network acl entry with deny user" )
          try {
            deleteNetworkAclEntry( new DeleteNetworkAclEntryRequest(
                networkAclId: networkAclId,
                ruleNumber: 200,
                egress: false
            ) )
            assertThat( false, "Expected delete failure for user without permission to delete network acl entry resource in vpc")
          } catch( Exception e ) {
            print( "Expected failure for network acl entry delete denied ${e}" )
          }

          print( "Deleting network acl with deny user" )
          try {
            deleteNetworkAcl( new DeleteNetworkAclRequest(
                networkAclId: networkAclId
            ) )
            assertThat( false, "Expected delete failure for user without permission to delete network acl resource in vpc")
          } catch( Exception e ) {
            print( "Expected failure for network acl delete denied ${e}" )
          }

          void
        }

        getEC2Client( vpcPermCredentials ).with {
          print( "Deleting network acl entry with allow user" )
          deleteNetworkAclEntry( new DeleteNetworkAclEntryRequest(
              networkAclId: networkAclId,
              ruleNumber: 200,
              egress: false
          ) )

          print( "Deleting network acl with allow user" )
          deleteNetworkAcl( new DeleteNetworkAclRequest(
              networkAclId: networkAclId
          ) )

          void
        }

        print( "Creating route table in vpc ${vpcId}" )
        String routeTableId = createRouteTable( new CreateRouteTableRequest( vpcId: vpcId ) ).with {
          routeTable?.routeTableId
        }
        print( "Created route table with id ${routeTableId}" )
        cleanupTasks.add{
          print( "Deleting route table ${routeTableId}" )
          deleteRouteTable( new DeleteRouteTableRequest( routeTableId: routeTableId ) )
        }

        print( "Creating route in ${routeTableId}" )
        createRoute( new CreateRouteRequest(
            routeTableId: routeTableId,
            destinationCidrBlock: '0.0.0.0/0',
            gatewayId: internetGatewayId
        ) )

        getEC2Client( vpcDenyCredentials ).with {
          print( "Deleting route with deny user" )
          try {
            deleteRoute( new DeleteRouteRequest(
                routeTableId: routeTableId,
                destinationCidrBlock: '0.0.0.0/0',
            ) )
            assertThat( false, "Expected delete failure for user without permission to delete route resource in vpc")
          } catch( Exception e ) {
            print( "Expected failure for route delete denied ${e}" )
          }

          print( "Deleting route table with deny user" )
          try {
            deleteRouteTable( new DeleteRouteTableRequest(
                routeTableId: routeTableId
            ) )
            assertThat( false, "Expected delete failure for user without permission to delete route table resource in vpc")
          } catch( Exception e ) {
            print( "Expected failure for route table delete denied ${e}" )
          }

          void
        }

        getEC2Client( vpcPermCredentials ).with {
          print( "Deleting route with allow user" )
          deleteRoute( new DeleteRouteRequest(
              routeTableId: routeTableId,
              destinationCidrBlock: '0.0.0.0/0',
          ) )

          print( "Deleting route table with allow user" )
          deleteRouteTable( new DeleteRouteTableRequest(
              routeTableId: routeTableId
          ) )

          void
        }

        getEC2Client( vpcDenyCredentials ).with {
          print("Running instance with deny user")
          try {
            String instanceId = runInstances(new RunInstancesRequest(
                minCount: 1,
                maxCount: 1,
                imageId: imageId,
                keyName: keyName,
                subnetId: subnetId,
                networkInterfaces: [
                    new InstanceNetworkInterfaceSpecification(
                        deviceIndex: 0,
                        associatePublicIpAddress: true,
                        subnetId: subnetId
                    )
                ]
            )).with {
              reservation?.with {
                instances?.getAt(0)?.with {
                  instanceId
                }
              }
            }
            cleanupTasks.add{
              print( "Terminating instance ${instanceId}" )
              terminateInstances( new TerminateInstancesRequest( instanceIds: [ instanceId ] ) )

              print( "Waiting for instance ${instanceId} to terminate" )
              ( 1..25 ).find{
                sleep 5000
                print( "Waiting for instance ${instanceId} to terminate, waited ${it*5}s" )
                describeInstances( new DescribeInstancesRequest(
                    instanceIds: [ instanceId ],
                    filters: [ new Filter( name: "instance-state-name", values: [ "terminated" ] ) ]
                ) ).with {
                  reservations?.getAt( 0 )?.instances?.getAt( 0 )?.instanceId == instanceId
                }
              }
            }
            assertThat( false, "Expected run instances failure for user without permission to run instance resources in subnet")
          } catch ( Exception e )  {
            print( "Expected failure for run instances denied ${e}" )
          }

          void
        }

        getEC2Client( vpcPermCredentials ).with {
          print("Running instance with allow user")
          String instanceId = runInstances(new RunInstancesRequest(
              minCount: 1,
              maxCount: 1,
              imageId: imageId,
              keyName: keyName,
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      associatePublicIpAddress: true,
                      subnetId: subnetId
                  )
              ]
          )).with {
            reservation?.with {
              instances?.getAt(0)?.with {
                instanceId
              }
            }
          }
          print( "Instance running with identifier ${instanceId}" )
          cleanupTasks.add{
            print( "Terminating instance ${instanceId}" )
            terminateInstances( new TerminateInstancesRequest( instanceIds: [ instanceId ] ) )

            print( "Waiting for instance ${instanceId} to terminate" )
            ( 1..25 ).find{
              sleep 5000
              print( "Waiting for instance ${instanceId} to terminate, waited ${it*5}s" )
              describeInstances( new DescribeInstancesRequest(
                  instanceIds: [ instanceId ],
                  filters: [ new Filter( name: "instance-state-name", values: [ "terminated" ] ) ]
              ) ).with {
                reservations?.getAt( 0 )?.instances?.getAt( 0 )?.instanceId == instanceId
              }
            }
          }

          print( "Waiting for instance ${instanceId} to start" )
          ( 1..25 ).find{
            sleep 5000
            print( "Waiting for instance ${instanceId} to start, waited ${it*5}s" )
            describeInstances( new DescribeInstancesRequest(
                instanceIds: [ instanceId ],
                filters: [ new Filter( name: "instance-state-name", values: [ "running" ] ) ]
            ) ).with {
              reservations?.getAt( 0 )?.instances?.getAt( 0 )?.instanceId == instanceId
            }
          }

          void
        }
      }

      print( "Test complete" )
    } finally {
      // Attempt to clean up anything we created
      cleanupTasks.reverseEach { Runnable cleanupTask ->
        try {
          cleanupTask.run()
        } catch ( Exception e ) {
          e.printStackTrace()
        }
      }
    }
  }
}
