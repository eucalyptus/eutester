package com.eucalyptus.tests.awssdk

import com.amazonaws.AmazonServiceException
import com.amazonaws.Request
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.handlers.AbstractRequestHandler
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*
import com.amazonaws.services.identitymanagement.model.CreateAccessKeyRequest
import com.github.sjones4.youcan.youare.YouAre
import com.github.sjones4.youcan.youare.YouAreClient
import com.github.sjones4.youcan.youare.model.CreateAccountRequest
import com.github.sjones4.youcan.youare.model.DeleteAccountRequest
import com.github.sjones4.youcan.youare.model.PutAccountPolicyRequest
import com.github.sjones4.youcan.youprop.YouProp
import com.github.sjones4.youcan.youprop.YouPropClient
import com.github.sjones4.youcan.youprop.model.ModifyPropertyValueRequest

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests quotas and limits for EC2 VPC resources.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9616
 */
class TestEC2VPCQuotasLimits {

  private final String host
  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCQuotasLimits( ).EC2VPCQuotasLimitsTest( )
  }

  public TestEC2VPCQuotasLimits() {
    minimalInit()
    this.host = HOST_IP
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

  private YouProp getYouPropClient( final AWSCredentialsProvider credentials ) {
    final YouProp youProp = new YouPropClient( credentials )
    youProp.setEndpoint( cloudUri( "/services/Properties/" ) )
    youProp
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
  public void EC2VPCQuotasLimitsTest( ) throws Exception {
    final YouProp prop = getYouPropClient( credentials )

    // End discovery, start test
    final String namePrefix = UUID.randomUUID().toString() + "-"
    print( "Using resource prefix for test: ${namePrefix}" )

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      prop.with {
        print( "Updating cloud.vpc.networkaclspervpc to 2" )
        final String originalNetworkAclsPerVpc = modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.networkaclspervpc', value: '2' ) ).with {
          oldValue
        }
        print( "Old cloud.vpc.networkaclspervpc value was: ${originalNetworkAclsPerVpc}" )
        cleanupTasks.add {
          print( "Restoring cloud.vpc.networkaclspervpc: ${originalNetworkAclsPerVpc}" )
          modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.networkaclspervpc', value: originalNetworkAclsPerVpc ) )
        }

        print( "Updating cloud.vpc.routespertable to 5" )
        final String originalRoutesPerRouteTable = modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.routespertable', value: '5' ) ).with {
          oldValue
        }
        print( "Old cloud.vpc.routespertable value was: ${originalRoutesPerRouteTable}" )
        cleanupTasks.add {
          print( "Restoring cloud.vpc.networkaclspervpc: ${originalRoutesPerRouteTable}" )
          modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.routespertable', value: originalRoutesPerRouteTable ) )
        }

        print( "Updating cloud.vpc.routetablespervpc to 2" )
        final String originalRouteTablesPerVpc = modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.routetablespervpc', value: '2' ) ).with {
          oldValue
        }
        print( "Old cloud.vpc.routetablespervpc value was: ${originalRouteTablesPerVpc}" )
        cleanupTasks.add {
          print( "Restoring cloud.vpc.routetablespervpc: ${originalRouteTablesPerVpc}" )
          modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.routetablespervpc', value: originalRouteTablesPerVpc ) )
        }

        print( "Updating cloud.vpc.rulespernetworkacl to 5" )
        final String originalRulesPerNetworkAcl = modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.rulespernetworkacl', value: '5' ) ).with {
          oldValue
        }
        print( "Old cloud.vpc.rulespernetworkacl value was: ${originalRulesPerNetworkAcl}" )
        cleanupTasks.add {
          print( "Restoring cloud.vpc.rulespernetworkacl: ${originalRulesPerNetworkAcl}" )
          modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.rulespernetworkacl', value: originalRulesPerNetworkAcl ) )
        }

        print( "Updating cloud.vpc.rulespersecuritygroup to 6" )
        final String originalRulesPerSecurityGroup = modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.rulespersecuritygroup', value: '5' ) ).with {
          oldValue
        }
        print( "Old cloud.vpc.rulespersecuritygroup value was: ${originalRulesPerSecurityGroup}" )
        cleanupTasks.add {
          print( "Restoring cloud.vpc.rulespersecuritygroup: ${originalRulesPerSecurityGroup}" )
          modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.rulespersecuritygroup', value: originalRulesPerSecurityGroup ) )
        }

        print( "Updating cloud.vpc.securitygroupspernetworkinterface to 3" )
        final String originalSecurityGroupsPerNetworkInterface = modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.securitygroupspernetworkinterface', value: '3' ) ).with {
          oldValue
        }
        print( "Old cloud.vpc.securitygroupspernetworkinterface value was: ${originalSecurityGroupsPerNetworkInterface}" )
        cleanupTasks.add {
          print( "Restoring cloud.vpc.securitygroupspernetworkinterface: ${originalSecurityGroupsPerNetworkInterface}" )
          modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.securitygroupspernetworkinterface', value: originalSecurityGroupsPerNetworkInterface ) )
        }

        print( "Updating cloud.vpc.securitygroupspervpc to 5" )
        final String originalSecurityGroupsPerVpc = modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.securitygroupspervpc', value: '5' ) ).with {
          oldValue
        }
        print( "Old cloud.vpc.securitygroupspervpc value was: ${originalSecurityGroupsPerVpc}" )
        cleanupTasks.add {
          print( "Restoring cloud.vpc.securitygroupspervpc: ${originalSecurityGroupsPerVpc}" )
          modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.securitygroupspervpc', value: originalSecurityGroupsPerVpc ) )
        }

        print( "Updating cloud.vpc.subnetspervpc to 2" )
        final String subnetsPerVpc = modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.subnetspervpc', value: '2' ) ).with {
          oldValue
        }
        print( "Old cloud.vpc.subnetspervpc value was: ${subnetsPerVpc}" )
        cleanupTasks.add {
          print( "Restoring cloud.vpc.subnetspervpc: ${subnetsPerVpc}" )
          modifyPropertyValue( new ModifyPropertyValueRequest( name: 'cloud.vpc.subnetspervpc', value: subnetsPerVpc ) )
        }
      }

      AWSCredentialsProvider vpcAccountCredentials = null
      final YouAre youAre = getYouAreClient( credentials )
      youAre.with {
        final String accountName = "${namePrefix}vpc-test-account"
        print( "Creating account for quota testing: ${accountName}" )
        String adminAccountNumber = createAccount( new CreateAccountRequest( accountName: accountName ) ).with {
          account?.accountId
        }
        assertThat( adminAccountNumber != null, "Expected account number" )
        print( "Created admin account with number: ${adminAccountNumber}" )
        cleanupTasks.add {
          print( "Deleting admin account: ${accountName}" )
          deleteAccount( new DeleteAccountRequest( accountName: accountName, recursive: true ) )
        }

        print( "Creating access key for admin account: ${accountName}" )
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
        assertThat( vpcAccountCredentials != null, "Expected admin credentials" )
        print( "Created vpc account access key: ${vpcAccountCredentials.credentials.AWSAccessKeyId}" )

        print( "Creating quota policy for vpc account" )
        putAccountPolicy( new PutAccountPolicyRequest(
          accountName: accountName,
          policyName: 'vpc-quota-policy',
          policyDocument: """
            {
              "Statement":[
                  {
                    "Effect":"Limit",
                    "Action":"ec2:CreateVpc",
                    "Resource":"*",
                    "Condition":{
                      "NumericLessThanEquals":{
                        "ec2:quota-vpcnumber":"3"
                      }
                    }
                  },
                  {
                    "Effect":"Limit",
                    "Action":"ec2:CreateInternetGateway",
                    "Resource":"*",
                    "Condition":{
                      "NumericLessThanEquals":{
                        "ec2:quota-internetgatewaynumber":"3"
                      }
                    }
                  },
              ]
            }
          """.stripIndent( )
        ) )

        void
      }

      final AmazonEC2 ec2 = getEC2Client( vpcAccountCredentials )
      ec2.with{
        print( 'Creating internet gateway 1' )
        String internetGatewayId = createInternetGateway( new CreateInternetGatewayRequest( ) ).with {
          internetGateway?.internetGatewayId
        }
        print( "Created internet gateway 1 with id ${internetGatewayId}" )
        cleanupTasks.add{
          print( "Deleting internet gateway 1 ${internetGatewayId}" )
          deleteInternetGateway( new DeleteInternetGatewayRequest( internetGatewayId: internetGatewayId ) )
        }

        print( 'Creating internet gateway 2' )
        String internetGatewayId2 = createInternetGateway( new CreateInternetGatewayRequest( ) ).with {
          internetGateway?.internetGatewayId
        }
        print( "Created internet gateway 2 with id ${internetGatewayId2}" )
        cleanupTasks.add{
          print( "Deleting internet gateway 2 ${internetGatewayId2}" )
          deleteInternetGateway( new DeleteInternetGatewayRequest( internetGatewayId: internetGatewayId2 ) )
        }

        try {
          print( 'Creating internet gateway 3' )
          String internetGatewayId3 = createInternetGateway( new CreateInternetGatewayRequest( ) ).with {
            internetGateway?.internetGatewayId
          }
          print( "Created internet gateway 3 with id ${internetGatewayId3}" )
          cleanupTasks.add{
            print( "Deleting internet gateway 3 ${internetGatewayId3}" )
            deleteInternetGateway( new DeleteInternetGatewayRequest( internetGatewayId: internetGatewayId3 ) )
          }
          assertThat( false, "Expected internet gateway creation to fail due to quota")
        } catch( AmazonServiceException exception ) {
          println( "Internet gateway 3 creation failed (expected), with error: " + exception )
          assertThat( exception.errorCode == 'InternetGatewayLimitExceeded', "Expected internet gateway create to fail with InternetGatewayLimitExceeded, but was: ${exception.errorCode}" )
        }

        print( 'Creating VPC 1' )
        String vpcId_1 = createVpc( new CreateVpcRequest( cidrBlock: '10.1.0.0/16' ) ).with {
          vpc?.vpcId
        }
        print( "Created VPC 1 with id ${vpcId_1}" )
        cleanupTasks.add{
          print( "Deleting VPC 1 ${vpcId_1}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId_1 ) )
        }

        print( 'Creating VPC 2' )
        String vpcId_2 = createVpc( new CreateVpcRequest( cidrBlock: '10.2.2.0/24' ) ).with {
          vpc?.vpcId
        }
        print( "Created VPC 2 with id ${vpcId_2}" )
        cleanupTasks.add{
          print( "Deleting VPC 2 ${vpcId_2}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId_2 ) )
        }

        try {
          print( 'Creating VPC 3' )
          String vpcId_3 = createVpc( new CreateVpcRequest( cidrBlock: '10.3.2.0/24' ) ).with {
            vpc?.vpcId
          }
          print( "Created VPC 3 with id ${vpcId_3}" )
          cleanupTasks.add{
            print( "Deleting VPC 2 ${vpcId_3}" )
            deleteVpc( new DeleteVpcRequest( vpcId: vpcId_3 ) )
          }
          assertThat( false, "Expected VPC creation to fail due to quota")
        } catch( AmazonServiceException exception ) {
          println( "VPC 3 creation failed (expected), with error: " + exception )
          assertThat( exception.errorCode == 'VpcLimitExceeded', "Expected vpc create to fail with VpcLimitExceeded, but was: ${exception.errorCode}" )
        }

        print( 'Creating subnet 1' )
        String subnetId1 = createSubnet( new CreateSubnetRequest( vpcId: vpcId_1, cidrBlock: '10.1.1.0/24' ) ).with {
          subnet?.subnetId
        }
        print( "Created subnet 1 with id ${subnetId1}" )
        cleanupTasks.add{
          print( "Deleting subnet 1 ${subnetId1}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId1 ) )
        }

        print( 'Creating subnet 2' )
        String subnetId2 = createSubnet( new CreateSubnetRequest( vpcId: vpcId_1, cidrBlock: '10.1.2.0/24' ) ).with {
          subnet?.subnetId
        }
        print( "Created subnet 2 with id ${subnetId2}" )
        cleanupTasks.add{
          print( "Deleting subnet 2 ${subnetId2}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId2 ) )
        }

        try {
          print( 'Creating subnet 3' )
          String subnetId3 = createSubnet( new CreateSubnetRequest( vpcId: vpcId_1, cidrBlock: '10.1.3.0/24' ) ).with {
            subnet?.subnetId
          }
          print( "Created subnet 3 with id ${subnetId3}" )
          cleanupTasks.add{
            print( "Deleting subnet 3 ${subnetId3}" )
            deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId3 ) )
          }
          assertThat( false, "Expected subnet creation to fail due to limit")
        } catch( AmazonServiceException exception ) {
          println( "Subnet 3 creation failed (expected), with error: " + exception )
          assertThat( exception.errorCode == 'SubnetLimitExceeded', "Expected subnet create to fail with SubnetLimitExceeded, but was: ${exception.errorCode}" )
        }

        print( "Creating network ACL 1" )
        String networkAcl1 = createNetworkAcl( new CreateNetworkAclRequest( vpcId: vpcId_1 ) ).with{
          networkAcl?.networkAclId
        }
        print( "Created network ACL 1 with id ${networkAcl1}" )
        cleanupTasks.add{
          print( "Deleting network ACL 1 ${networkAcl1}" )
          deleteNetworkAcl( new DeleteNetworkAclRequest( networkAclId: networkAcl1 ) )
        }

        try {
          print( "Creating network ACL 2" )
          String networkAcl2 = createNetworkAcl( new CreateNetworkAclRequest( vpcId: vpcId_1 ) ).with{
            networkAcl?.networkAclId
          }
          print( "Created network ACL 2 with id ${networkAcl2}" )
          cleanupTasks.add{
            print( "Deleting network ACL 2 ${networkAcl2}" )
            deleteNetworkAcl( new DeleteNetworkAclRequest( networkAclId: networkAcl2 ) )
          }
          assertThat( false, "Expected network ACL creation to fail due to limit")
        } catch( AmazonServiceException exception ) {
          println("Network ACL 2 creation failed (expected), with error: " + exception)
          assertThat(exception.errorCode == 'NetworkAclLimitExceeded', "Expected network ACL create to fail with NetworkAclLimitExceeded, but was: ${exception.errorCode}")
        }

        print( "Creating route table 1" )
        String routeTable1 = createRouteTable( new CreateRouteTableRequest( vpcId: vpcId_1 ) ).with{
          routeTable?.routeTableId
        }
        print( "Created route table 1 with id ${routeTable1}" )
        cleanupTasks.add{
          print( "Deleting route table 1 ${routeTable1}" )
          deleteRouteTable( new DeleteRouteTableRequest( routeTableId: routeTable1 ) )
        }

        try {
          print( "Creating route table 2" )
          String routeTable2 = createRouteTable( new CreateRouteTableRequest( vpcId: vpcId_1 ) ).with{
            routeTable?.routeTableId
          }
          print( "Created route table 2 with id ${routeTable2}" )
          cleanupTasks.add{
            print( "Deleting route table 2 ${routeTable2}" )
            deleteRouteTable( new DeleteRouteTableRequest( routeTableId: routeTable2 ) )
          }
          assertThat( false, "Expected route table creation to fail due to limit")
        } catch( AmazonServiceException exception ) {
          println("Route table 2 creation failed (expected), with error: " + exception)
          assertThat(exception.errorCode == 'RouteTableLimitExceeded', "Expected route table create to fail with RouteTableLimitExceeded, but was: ${exception.errorCode}")
        }

        String securityGroupId1 = null
        ( 1 .. 4 ).each { int number ->
          print( "Creating security group ${number}" )
          String securityGroupId = createSecurityGroup( new CreateSecurityGroupRequest(
              vpcId: vpcId_1,
              groupName: "${namePrefix}Group${number}",
              description: "quota and limits test security group"
          ) ).with{
            groupId
          }
          print( "Created security group ${number} with id ${securityGroupId}" )
          if ( securityGroupId1 == null ) securityGroupId1 = securityGroupId
          cleanupTasks.add{
            print( "Deleting security group ${number} ${securityGroupId}" )
            deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: securityGroupId ) )
          }
        }

        try {
          print( "Creating security group 5" )
          String securityGroupId = createSecurityGroup( new CreateSecurityGroupRequest(
              vpcId: vpcId_1,
              groupName: "${namePrefix}Group5",
              description: "quota and limits test security group"
          ) ).with{
            groupId
          }
          print( "Created security group 5 with id ${securityGroupId}" )
          cleanupTasks.add{
            print( "Deleting security group 5 ${securityGroupId}" )
            deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: securityGroupId ) )
          }
          assertThat( false, "Expected security group creation to fail due to limit")
        } catch( AmazonServiceException exception ) {
          println("Security group 5 creation failed (expected), with error: " + exception)
          assertThat(exception.errorCode == 'SecurityGroupLimitExceeded', "Expected security group create to fail with SecurityGroupLimitExceeded, but was: ${exception.errorCode}")
        }

        ( 1 .. 4 ).each { int number ->
          print( "Creating route ${number}" )
          createRoute( new CreateRouteRequest( routeTableId: routeTable1, destinationCidrBlock: "${number}.0.0.0/8", gatewayId: internetGatewayId ) )
        }
        try {
          print( "Creating route 5" )
          createRoute( new CreateRouteRequest( routeTableId: routeTable1, destinationCidrBlock: "6.0.0.0/8", gatewayId: internetGatewayId ) )
          assertThat( false, "Expected route creation to fail due to limit")
        } catch( AmazonServiceException exception ) {
          println("Route 5 creation failed (expected), with error: " + exception)
          assertThat(exception.errorCode == 'RouteLimitExceeded', "Expected route create to fail with RouteLimitExceeded, but was: ${exception.errorCode}")
        }

        ( 1 .. 4 ).each { int number ->
          print( "Creating network acl rule ${number}" )
          createNetworkAclEntry( new CreateNetworkAclEntryRequest(
              networkAclId: networkAcl1,
              ruleNumber: number,
              ruleAction: 'allow',
              egress: false,
              cidrBlock: '0.0.0.0/0',
              protocol: -1          ) )
        }
        try {
          print( "Creating network acl rule 5" )
          createNetworkAclEntry( new CreateNetworkAclEntryRequest(
              networkAclId: networkAcl1,
              ruleNumber: 5,
              ruleAction: 'allow',
              egress: false,
              cidrBlock: '0.0.0.0/0',
              protocol: -1          ) )
          assertThat( false, "Expected network acl entry creation to fail due to limit")
        } catch( AmazonServiceException exception ) {
          println("Network acl entry 5 creation failed (expected), with error: " + exception)
          assertThat(exception.errorCode == 'NetworkAclEntryLimitExceeded', "Expected network acl entry create to fail with NetworkAclEntryLimitExceeded, but was: ${exception.errorCode}")
        }

        ( 1 .. 4 ).each { int number ->
          print( "Creating security group rule ${number}" )
          authorizeSecurityGroupEgress( new AuthorizeSecurityGroupEgressRequest(
              groupId: securityGroupId1,
              ipPermissions: [
                  new IpPermission(
                      ipProtocol: number,
                      ipRanges: [ '0.0.0.0/0' ]
                  )
              ]
          ) )
        }
        try {
          print( "Creating security group rule 5 (egress)" )
          authorizeSecurityGroupEgress( new AuthorizeSecurityGroupEgressRequest(
              groupId: securityGroupId1,
              ipPermissions: [
                  new IpPermission(
                      ipProtocol: 6,
                      ipRanges: [ '0.0.0.0/0' ]
                  )
              ]
          ) )
          assertThat( false, "Expected security group rule creation to fail due to limit")
        } catch( AmazonServiceException exception ) {
          println("Security group rule 6 creation failed (expected), with error: " + exception)
        }

        try {
          print( "Creating security group rule 6 (ingress)" )
          authorizeSecurityGroupIngress( new AuthorizeSecurityGroupIngressRequest(
              groupId: securityGroupId1,
              ipPermissions: [
                  new IpPermission(
                      ipProtocol: 6,
                      ipRanges: [ '0.0.0.0/0' ]
                  )
              ]
          ) )
          assertThat( false, "Expected security group rule creation to fail due to limit")
        } catch( AmazonServiceException exception ) {
          println("Security group rule 6 creation failed (expected), with error: " + exception)
        }

        void
      }

      print( "Test complete" )
    } finally {
      // Attempt to clean up anything we created
      cleanupTasks.reverseEach { Runnable cleanupTask ->
        try {
          cleanupTask.run()
        } catch ( Exception e ) {
          // Some not-found errors are expected here so may need to be suppressed
          e.printStackTrace()
        }
      }
    }
  }
}
