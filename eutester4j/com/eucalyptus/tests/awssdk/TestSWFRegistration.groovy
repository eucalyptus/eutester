package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.simpleworkflow.AmazonSimpleWorkflow
import com.amazonaws.services.simpleworkflow.AmazonSimpleWorkflowClient
import com.amazonaws.services.simpleworkflow.model.ActivityType
import com.amazonaws.services.simpleworkflow.model.DeprecateActivityTypeRequest
import com.amazonaws.services.simpleworkflow.model.DeprecateDomainRequest
import com.amazonaws.services.simpleworkflow.model.DeprecateWorkflowTypeRequest
import com.amazonaws.services.simpleworkflow.model.DescribeActivityTypeRequest
import com.amazonaws.services.simpleworkflow.model.DescribeDomainRequest
import com.amazonaws.services.simpleworkflow.model.DescribeWorkflowTypeRequest
import com.amazonaws.services.simpleworkflow.model.DomainDeprecatedException
import com.amazonaws.services.simpleworkflow.model.ListActivityTypesRequest
import com.amazonaws.services.simpleworkflow.model.ListDomainsRequest
import com.amazonaws.services.simpleworkflow.model.ListWorkflowTypesRequest
import com.amazonaws.services.simpleworkflow.model.RegisterActivityTypeRequest
import com.amazonaws.services.simpleworkflow.model.RegisterDomainRequest
import com.amazonaws.services.simpleworkflow.model.RegisterWorkflowTypeRequest
import com.amazonaws.services.simpleworkflow.model.TaskList
import com.amazonaws.services.simpleworkflow.model.TypeDeprecatedException
import com.amazonaws.services.simpleworkflow.model.WorkflowType

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;

/**
 * This application tests registration actions for SWF.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9618
 */
class TestSWFRegistration {

  private final String host;
  private final AWSCredentialsProvider credentials


  public static void main( String[] args ) throws Exception {
    new TestSWFRegistration( ).TestSWFRegistrationTest( )
  }

  public TestSWFRegistration(){
    minimalInit()
    this.host = HOST_IP
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
            .resolve( servicePath )
            .toString()
  }

  private AmazonSimpleWorkflow getSWFClient( final AWSCredentialsProvider credentials ) {
    final AmazonSimpleWorkflow swf = new AmazonSimpleWorkflowClient( credentials )
    swf.setEndpoint( cloudUri( "/services/SimpleWorkflow" ) )
    swf
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
  public void TestSWFRegistrationTest( ) throws Exception {
    final AmazonSimpleWorkflow swf = getSWFClient( credentials )

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      final String namePrefix = UUID.randomUUID().toString() + "-";
      print( "Using prefix for test: " + namePrefix );

      swf.with{
        String domainName = "${namePrefix}domain"
        print( "Registering domain ${domainName}" )
        registerDomain( new RegisterDomainRequest(
                name: domainName,
                description: 'test domain',
                workflowExecutionRetentionPeriodInDays: 1 ) )
        cleanupTasks.add{
          print( "Deprecating domain ${domainName}" )
          deprecateDomain( new DeprecateDomainRequest( name: domainName ) )
        }

        print( 'Listing domains' )
        listDomains( new ListDomainsRequest(  ) ).with {
          print( domainInfos.toString( ) )
          assertThat( domainInfos.collect{ it.name }.contains( domainName ), "Domain not found in listing" )
          domainInfos.find{ it.name == domainName }.with {
            assertThat( description == 'test domain', "Expected domain description 'test domain', but was: ${description}" )
            assertThat( status == 'REGISTERED', "Expected domain status 'REGISTERED', but was: ${status}" )
          }
        }

        print( "Describing domain ${domainName}" )
        describeDomain( new DescribeDomainRequest( name: domainName ) ).with {
          assertThat( configuration != null, "Expected domain configuration" )
          configuration.with {
            assertThat( workflowExecutionRetentionPeriodInDays == '1', "Expected workflow retention 1, but was ${workflowExecutionRetentionPeriodInDays}" )
          }
          assertThat( domainInfo != null, "Expected domain info" )
          domainInfo.with {
            assertThat( name == domainName, "Unexpected domain name: ${name}" )
            assertThat( description == 'test domain', "Expected domain description 'test domain', but was: ${description}" )
            assertThat( status == 'REGISTERED', "Expected domain status 'REGISTERED', but was: ${status}" )
          }
        }

        String activityTypeName = "${namePrefix}activity-type"
        print( "Registering activity type ${activityTypeName}" )
        registerActivityType( new RegisterActivityTypeRequest(
                domain: domainName,
                name: activityTypeName,
                version: '1',
                description: 'test activity type',
                defaultTaskList: new TaskList( name: 'activity-task-list' ),
                defaultTaskHeartbeatTimeout: '1',
                defaultTaskScheduleToCloseTimeout: '2',
                defaultTaskStartToCloseTimeout: '3',
                defaultTaskScheduleToStartTimeout: '4'
        ) )
        cleanupTasks.add{
          print( "Deprecating activity type ${domainName}" )
          deprecateActivityType( new DeprecateActivityTypeRequest( domain: domainName, activityType: new ActivityType( name: activityTypeName, version: '1' ) ))
        }

        print( 'Listing activity types' )
        listActivityTypes( new ListActivityTypesRequest( domain: domainName ) ).with {
          print( typeInfos.toString( ) )
          assertThat( typeInfos.collect{ it.activityType.name }.contains( activityTypeName ), "Activity type not found in listing" )
          typeInfos.find{ it.activityType.name == activityTypeName }.with {
            assertThat( description == 'test activity type', "Expected activity type description 'test activity type', but was: ${description}" )
            assertThat( activityType.version == '1', "Expected activity type version '1', but was: ${activityType.version}" )
            assertThat( status == 'REGISTERED', "Expected activity type status 'REGISTERED', but was: ${status}" )
            assertThat( creationDate != null, "Expected activity type creation date" )
            assertThat( deprecationDate == null, "Unexpected activity type deprecation date: ${deprecationDate}" )
          }
        }

        print( "Describing activity type ${activityTypeName}" )
        describeActivityType( new DescribeActivityTypeRequest( domain: domainName, activityType: new ActivityType( name: activityTypeName, version: '1' ) )).with {
          assertThat( configuration != null, "Expected activity type configuration" )
          configuration.with {
            assertThat( defaultTaskList.name == 'activity-task-list', "Expected activity type task list 'activity-task-list', but was: ${defaultTaskList.name}" )
            assertThat( defaultTaskHeartbeatTimeout == '1', "Expected activity type heartbeat timeout '1', but was: ${defaultTaskHeartbeatTimeout}" )
            assertThat( defaultTaskScheduleToCloseTimeout == '2', "Expected activity type schedule to close timeout '2', but was: ${defaultTaskScheduleToCloseTimeout}" )
            assertThat( defaultTaskStartToCloseTimeout == '3', "Expected activity type start to close timeout '3', but was: ${defaultTaskStartToCloseTimeout}" )
            assertThat( defaultTaskScheduleToStartTimeout == '4', "Expected activity type schedule to start '4', but was: ${defaultTaskScheduleToStartTimeout}" )
          }
          assertThat( typeInfo != null, "Expected activity type info" )
          typeInfo.with {
            assertThat( description == 'test activity type', "Expected activity type description 'test activity type', but was: ${description}" )
            assertThat( activityType.name == activityTypeName, "Expected activity type name '${activityTypeName}', but was: ${activityType.name}" )
            assertThat( activityType.version == '1', "Expected activity type version '1', but was: ${activityType.version}" )
            assertThat( status == 'REGISTERED', "Expected activity type status 'REGISTERED', but was: ${status}" )
            assertThat( creationDate != null, "Expected activity type creation date" )
            assertThat( deprecationDate == null, "Unexpected activity type deprecation date: ${deprecationDate}" )
          }
        }

        print( "Deprecating activity type ${activityTypeName}" )
        deprecateActivityType( new DeprecateActivityTypeRequest( domain: domainName, activityType: new ActivityType( name: activityTypeName, version: '1' ) ))

        print( 'Listing activity types to verify deprecated' )
        listActivityTypes( new ListActivityTypesRequest( domain: domainName ) ) .with {
          assertThat( typeInfos.collect{ it.activityType.name }.contains( activityTypeName ), "Activity type not found in listing" )
          typeInfos.find{ it.activityType.name == activityTypeName }.with {
            assertThat( status == 'DEPRECATED', "Expected activity type status 'DEPRECATED', but was: ${status}" )
          }
        }

        String workflowTypeName = "${namePrefix}workflow-type"
        print( "Registering workflow type ${workflowTypeName}" )
        registerWorkflowType( new RegisterWorkflowTypeRequest(
                domain: domainName,
                name: workflowTypeName,
                version: '1',
                description: 'test workflow type',
                defaultTaskList: new TaskList( name: 'workflow-task-list' ),
                defaultChildPolicy: 'TERMINATE',
                defaultTaskStartToCloseTimeout: '1',
                defaultExecutionStartToCloseTimeout: '2'
        ) )
        cleanupTasks.add{
          print( "Deprecating workflow type ${domainName}" )
          deprecateWorkflowType( new DeprecateWorkflowTypeRequest( domain: domainName, workflowType: new WorkflowType( name: workflowTypeName, version: '1' ) ))
        }

        print( 'Listing workflow types' )
        listWorkflowTypes( new ListWorkflowTypesRequest( domain: domainName ) ).with {
          print( typeInfos.toString( ) )
          assertThat( typeInfos.collect{ it.workflowType.name }.contains( workflowTypeName ), "Workflow type not found in listing" )
          typeInfos.find{ it.workflowType.name == workflowTypeName }.with {
            assertThat( description == 'test workflow type', "Expected workflow type description 'test workflow type', but was: ${description}" )
            assertThat( workflowType.version == '1', "Expected workflow type version '1', but was: ${workflowType.version}" )
            assertThat( status == 'REGISTERED', "Expected workflow type status 'REGISTERED', but was: ${status}" )
            assertThat( creationDate != null, "Expected workflow type creation date" )
            assertThat( deprecationDate == null, "Unexpected workflow type deprecation date: ${deprecationDate}" )
          }
        }

        print( "Describing workflow type ${workflowTypeName}" )
        describeWorkflowType( new DescribeWorkflowTypeRequest( domain: domainName, workflowType: new WorkflowType( name: workflowTypeName, version: '1' ) )).with {
          assertThat( configuration != null, "Expected workflow type configuration" )
          configuration.with {
            assertThat( defaultTaskList.name == 'workflow-task-list', "Expected workflow type task list 'workflow-task-list', but was: ${defaultTaskList.name}" )
            assertThat( defaultChildPolicy == 'TERMINATE', "Expected workflow type child policy 'TERMINATE', but was: ${defaultTaskStartToCloseTimeout}" )
            assertThat( defaultTaskStartToCloseTimeout == '1', "Expected workflow type task start to close timeout '1', but was: ${defaultTaskStartToCloseTimeout}" )
            assertThat( defaultExecutionStartToCloseTimeout == '2', "Expected workflow type exec start to close timeout '2', but was: ${defaultExecutionStartToCloseTimeout}" )
          }
          assertThat( typeInfo != null, "Expected workflow type info" )
          typeInfo.with {
            assertThat( description == 'test workflow type', "Expected workflow type description 'test workflow type', but was: ${description}" )
            assertThat( workflowType.name == workflowTypeName, "Expected workflow type version '${workflowTypeName}', but was: ${workflowType.name}" )
            assertThat( workflowType.version == '1', "Expected workflow type version '1', but was: ${workflowType.version}" )
            assertThat( status == 'REGISTERED', "Expected workflow type status 'REGISTERED', but was: ${status}" )
            assertThat( creationDate != null, "Expected workflow type creation date" )
            assertThat( deprecationDate == null, "Unexpected workflow type deprecation date: ${deprecationDate}" )
          }
        }

        print( "Deprecating workflow type ${workflowTypeName}" )
        deprecateWorkflowType( new DeprecateWorkflowTypeRequest( domain: domainName, workflowType: new WorkflowType( name: workflowTypeName, version: '1' ) ))

        print( 'Listing workflow types to verify deprecated' )
        listWorkflowTypes( new ListWorkflowTypesRequest( domain: domainName ) ) .with {
          assertThat( typeInfos.collect{ it.workflowType.name }.contains( workflowTypeName ), "Activity type not found in listing" )
          typeInfos.find{ it.workflowType.name == workflowTypeName }.with {
            assertThat( status == 'DEPRECATED', "Expected workflow type status 'DEPRECATED', but was: ${status}" )
          }
        }

        print( "Deprecating domain ${domainName}" )
        deprecateDomain( new DeprecateDomainRequest( name: domainName ) )

        print( 'Listing domains to verify deprecated' )
        listDomains( new ListDomainsRequest(  ) ).with {
          assertThat( domainInfos.collect{ it.name }.contains( domainName ), "Domain not found in listing" )
          domainInfos.find{ it.name == domainName }.with {
            assertThat( status == 'DEPRECATED', "Expected domain status 'DEPRECATED', but was: ${status}" )
          }
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
