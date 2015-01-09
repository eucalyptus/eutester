package com.eucalyptus.tests.awssdk

import com.amazonaws.Request
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.handlers.AbstractRequestHandler
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*
import com.amazonaws.services.identitymanagement.model.CreateAccessKeyRequest
import com.github.sjones4.youcan.youare.YouAreClient
import com.github.sjones4.youcan.youare.model.CreateAccountRequest
import com.github.sjones4.youcan.youare.model.DeleteAccountRequest
import com.github.sjones4.youcan.youprop.YouProp
import com.github.sjones4.youcan.youprop.YouPropClient
import com.github.sjones4.youcan.youprop.model.ModifyPropertyValueRequest

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;

/**
 * This application tests EC2 VPC default VPC.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9613
 */
class TestEC2VPCDefaultVPC {

  private final String host
  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
      new TestEC2VPCDefaultVPC().EC2VPCDefaultVPCTest()
  }

  public TestEC2VPCDefaultVPC(){
    minimalInit()
    this.host = HOST_IP
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
            .resolve( servicePath )
            .toString()
  }

  private AmazonEC2Client getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2Client ec2 = new AmazonEC2Client( credentials )
    ec2.setEndpoint( cloudUri( "/services/compute" ) )
    ec2
  }

  private YouProp getYouPropClient( final AWSCredentialsProvider credentials ) {
    final YouProp youProp = new YouPropClient( credentials )
    youProp.setEndpoint( cloudUri( "/services/Properties/" ) )
    youProp
  }

  private YouAreClient getYouAreClient( final AWSCredentialsProvider credentials ) {
    final YouAreClient euare = new YouAreClient( credentials )
    euare.setEndpoint( cloudUri( "/services/Euare" ) )
    euare
  }

  private YouAreClient getYouAreClient( final AWSCredentialsProvider credentials,
                                        final String asAccount ) {
    final YouAreClient euare = new YouAreClient( credentials )
    euare.addRequestHandler( new AbstractRequestHandler(){
      public void beforeRequest(final Request<?> request) {
        request.addParameter( "DelegateAccount", asAccount )
      }
    } );
    euare.setEndpoint( cloudUri( "/services/Euare" ) )
    euare;
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
  public void EC2VPCDefaultVPCTest( ) throws Exception {
    final YouProp prop = getYouPropClient( credentials )
    final YouAreClient euare = getYouAreClient( credentials );

    final String namePrefix = UUID.randomUUID().toString() + "-";
    print( "Using resource prefix for test: " + namePrefix );

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      prop.with {
        print("Updating cloud.vpc.defaultvpc to true")
        final String originalDefaultVpc = modifyPropertyValue(new ModifyPropertyValueRequest(name: 'cloud.vpc.defaultvpc', value: 'true')).with {
          oldValue
        }
        print("Old cloud.vpc.defaultvpc value was: ${originalDefaultVpc}")
        cleanupTasks.add {
          print("Restoring cloud.vpc.defaultvpc: ${originalDefaultVpc}")
          modifyPropertyValue(new ModifyPropertyValueRequest(name: 'cloud.vpc.defaultvpc', value: originalDefaultVpc))
        }
      }

      final String accountName = namePrefix + "admin-account1";
      euare.with {
        // Create account to use for testing
        print( "Creating admin account: " + accountName );
        String adminAccountNumber = createAccount( new CreateAccountRequest( accountName: accountName ) ).with {
          account.accountId
        }
        assertThat( adminAccountNumber != null, "Expected account number" );
        print( "Created admin account with number: " + adminAccountNumber );
        cleanupTasks.add {
          print( "Deleting admin account: " + accountName );
          deleteAccount( new DeleteAccountRequest( accountName: accountName, recursive: true ) );
        }
      }

      // Get credentials for admin account
      print( "Creating access key for admin account: ${accountName}" )
      AWSCredentialsProvider adminCredentials = getYouAreClient( credentials, accountName ).with {
        createAccessKey( new CreateAccessKeyRequest( userName: "admin" ) ).with {
          accessKey?.with {
            new StaticCredentialsProvider( new BasicAWSCredentials( accessKeyId, secretAccessKey ) )
          }
        }
      }
      assertThat( adminCredentials != null, "Expected admin credentials" )
      print( "Created admin account access key: ${adminCredentials.credentials.AWSAccessKeyId}" )

      getEC2Client( adminCredentials ).with {
        print( "Finding default VPC" )
        String defaultVpcId = describeVpcs( new DescribeVpcsRequest(
                filters: [ new Filter( name: 'isDefault', values: [ 'true' ] ) ]
        ) ).with {
          assertThat( vpcs != null && vpcs.size( ) == 1, "Expected one VPC, but was: ${vpcs?.size( )}" )
          vpcs?.getAt( 0 )?.with {
            print( "Found default VPC: ${vpcId}" )
            assertThat( '172.31.0.0/16' == cidrBlock, "Expected cidr 172.31.0.0/16, but was: ${cidrBlock}")
            assertThat( isDefault, "Expected isDefault, but was: ${isDefault}" )
            vpcId
          }
        }

        print( "Verifying VPC attributes" )
        describeVpcAttribute( new DescribeVpcAttributeRequest(
                vpcId: defaultVpcId,
                attribute: 'enableDnsHostnames'
        ) ).with {
          assertThat( enableDnsHostnames, "Expected DNS hostnames to be enabled for ${defaultVpcId}, but was: ${enableDnsHostnames}" )
        }

        print( "Describing availability zones" )
        List<String> zones = describeAvailabilityZones( ).with {
          availabilityZones.collect{ it.zoneName }
        }
        print( "Found zones: ${zones}" )

        zones.each { String zone ->
          print( "Finding default subnet for zone: ${zone}" )
          describeSubnets( new DescribeSubnetsRequest(
                  filters: [
                          new Filter( name: 'default-for-az', values: [ 'true' ] ),
                          new Filter( name: 'availability-zone', values: [ zone ] )
                  ]
          ) ).with {
            assertThat( subnets != null && subnets.size( ) == 1, "Expected one subnets for zone ${zone}, but was: ${subnets?.size( )}" )
            subnets?.getAt( 0 )?.with {
              print( "Found default subnet for zone ${zone}: ${subnetId}" )
              assertThat( mapPublicIpOnLaunch, "Expected public IP mapping on launch, but was: ${mapPublicIpOnLaunch}" )
              assertThat( defaultForAz, "Expected defaultForAz, but was: ${defaultForAz}" )
              assertThat( defaultVpcId == vpcId, "Expected vpcId ${defaultVpcId}, but was: ${vpcId}" )
              assertThat( zone == availabilityZone, "Expected availabilityZone ${zone}, but was: ${availabilityZone}" )
            }
          }
        }

        print( "Finding internet gateway for default vpc ${defaultVpcId}" )
        String internetGatewayId = describeInternetGateways( new DescribeInternetGatewaysRequest(
                filters: [ new Filter( name: 'attachment.vpc-id', values: [ defaultVpcId ] ) ]
        ) ).with {
          assertThat( internetGateways != null && internetGateways.size() == 1, "Expected one internet gateway, but was: ${internetGateways?.size()}" )
          internetGateways?.getAt( 0 )?.internetGatewayId
        }
        print( "Found internet gateway ${internetGatewayId}" )

        print( "Verifying route for internet gateway" )
        describeRouteTables( new DescribeRouteTablesRequest(
                filters: [
                        new Filter( name: 'vpc-id', values: [ defaultVpcId ] ),
                        new Filter( name: 'association.main', values: [ 'true' ] )
                ]
        ) ).with {
          assertThat( routeTables != null && routeTables.size() == 1, "Expected one route table, but was: ${routeTables?.size()}" )
          routeTables?.getAt( 0 )?.with {
            print( "Found route table: ${routeTableId}" )
            List<Route> routes = routes.findAll { Route route -> route.gatewayId == internetGatewayId && route.destinationCidrBlock == '0.0.0.0/0' }
            assertThat( routes.size( ) == 1, "Expected default route to internet gateway ${internetGatewayId} for route table ${routeTableId}" )
          }
        }

        print( "Verifying address allocated in vpc domain" )
        String allocationId = allocateAddress( ).with {
          assertThat( 'vpc' == domain, "Expected domain vpc, but was: ${domain}" )
          allocationId
        }

        print( "Releasing address by allocation ${allocationId}" )
        releaseAddress( new ReleaseAddressRequest( allocationId: allocationId ) )

        print( "Verifying default vpc security group can be listed by name" )
        describeSecurityGroups( new DescribeSecurityGroupsRequest( groupNames: [ 'default' ] ) ).with {
          assertThat( securityGroups != null && securityGroups.size( ) == 1, "Expected one group, but was: ${securityGroups?.size()}" )
        }

        print( "Verifying that security groups are created in default vpc" )
        final String groupName = "${namePrefix}group-1";
        final String groupId = createSecurityGroup( new CreateSecurityGroupRequest( groupName: groupName, description: groupName )).with {
          groupId
        }
        print( "Created security group ${groupName} / ${groupId}" )
        cleanupTasks.add{
          print( "Deleting security group: ${groupId}" )
          deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: groupId ) )
        }
        describeSecurityGroups( new DescribeSecurityGroupsRequest( groupIds: [ groupId ] )).with {
          assertThat( securityGroups != null && securityGroups.size( ) == 1, "Expected one group, but was: ${securityGroups?.size()}" )
          securityGroups?.getAt( 0 )?.with {
            assertThat( vpcId != null, "Expected group in vpc" )
          }
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
