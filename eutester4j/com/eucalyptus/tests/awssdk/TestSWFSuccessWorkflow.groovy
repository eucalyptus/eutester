package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.simpleworkflow.AmazonSimpleWorkflow
import com.amazonaws.services.simpleworkflow.AmazonSimpleWorkflowClient
import com.amazonaws.services.simpleworkflow.model.*

import java.util.concurrent.TimeUnit

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;

/**
 * This application tests SWF functionality for successful workflows.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9619
 */
class TestSWFSuccessWorkflow {

  private final String host;
  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestSWFSuccessWorkflow( ).SWFSuccessWorkflowTest( )
  }

  public TestSWFSuccessWorkflow(){
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
  public void SWFSuccessWorkflowTest( ) throws Exception {
    final AmazonSimpleWorkflow swf = getSWFClient( credentials )

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      final String namePrefix = UUID.randomUUID().toString() + "-";
      print( "Using prefix for test: " + namePrefix );

      swf.with {
        String domainName = "${namePrefix}domain"
        print("Registering domain ${domainName}")
        registerDomain(new RegisterDomainRequest(
                name: domainName,
                description: 'test domain',
                workflowExecutionRetentionPeriodInDays: 1))
        cleanupTasks.add {
          print("Deprecating domain ${domainName}")
          deprecateDomain(new DeprecateDomainRequest(name: domainName))
        }

        String activityTypeName = "${namePrefix}activity-type"
        print("Registering activity type ${activityTypeName}")
        registerActivityType(new RegisterActivityTypeRequest(
                domain: domainName,
                name: activityTypeName,
                version: '1',
                description: 'test activity type',
                defaultTaskList: new TaskList(name: 'list'),
                defaultTaskHeartbeatTimeout: '60',
                defaultTaskScheduleToCloseTimeout: '60',
                defaultTaskStartToCloseTimeout: '60',
                defaultTaskScheduleToStartTimeout: '60'
        ))
        cleanupTasks.add {
          print("Deprecating activity type ${domainName}")
          deprecateActivityType(new DeprecateActivityTypeRequest(domain: domainName, activityType: new ActivityType(name: activityTypeName, version: '1')))
        }

        String workflowTypeName = "${namePrefix}workflow-type"
        print("Registering workflow type ${workflowTypeName}")
        registerWorkflowType(new RegisterWorkflowTypeRequest(
                domain: domainName,
                name: workflowTypeName,
                version: '1',
                description: 'test workflow type',
                defaultTaskList: new TaskList(name: 'list'),
                defaultChildPolicy: 'TERMINATE',
                defaultTaskStartToCloseTimeout: '60',
                defaultExecutionStartToCloseTimeout: '60'
        ))
        cleanupTasks.add {
          print("Deprecating workflow type ${domainName}")
          deprecateWorkflowType(new DeprecateWorkflowTypeRequest(domain: domainName, workflowType: new WorkflowType(name: workflowTypeName, version: '1')))
        }

        print( "Polling for decision task ${domainName}/list" )
        pollForDecisionTask(new PollForDecisionTaskRequest(
                domain: domainName,
                taskList: new TaskList(name: 'list'),
                identity: 'test-decider-1'
        ))?.with {
          assertThat( taskToken == null, "Expected no tasks" )
        }

        String workflowId = "${namePrefix}workflow-id"
        print( "Starting workflow execution ${workflowId}" )
        String runId = startWorkflowExecution(new StartWorkflowExecutionRequest(
                workflowId: workflowId,
                domain: domainName,
                workflowType: new WorkflowType( name: workflowTypeName, version: '1' ),
                tagList: [ 'tags', 'go', 'here' ],
                taskList: new TaskList( name: 'list' ),
                input: 'input-here',
        )).with {
          runId
        }
        assertThat( runId != null, "Expected run-id" )
        print( "Started workflow execution with runId: ${runId}" )

        print( "Polling for decision task ${domainName}/list-with-no-tasks" )
        pollForDecisionTask(new PollForDecisionTaskRequest(
                domain: domainName,
                taskList: new TaskList(name: 'list-with-no-tasks'),
                identity: 'test-decider-1'
        ))?.with {
          assertThat( taskToken == null, "Expected no tasks" )
        }

        print( "Polling for decision task ${domainName}/list" )
        String decisionTaskToken1 = pollForDecisionTask(new PollForDecisionTaskRequest(
                domain: domainName,
                taskList: new TaskList(name: 'list'),
                identity: 'test-decider-1'
        )).with {
          assertThat( previousStartedEventId == 0, "Expected no previous started event" )
          assertThat( startedEventId == 3, "Expected started event ID 3, but was ${startedEventId}" )
          assertThat( taskToken != null, "Expected task token" )
          assertThat( workflowExecution != null, "Expected workflow execution ")
          assertThat( workflowExecution.runId == runId, "Expected workflow execution runId ${runId}, but was: ${workflowExecution.runId}")
          assertThat( workflowExecution.workflowId == workflowId, "Expected workflow execution workflowId ${workflowId}, but was: ${workflowExecution.workflowId}")
          assertThat( workflowType != null, "Expected workflow type ")
          assertThat( workflowType.name == workflowTypeName, "Expected workflow type name ${workflowTypeName}, but was: ${workflowType.name}")
          assertThat( workflowType.version == '1', "Expected workflow type version 1, but was: ${workflowType.version}")
          assertThat( events != null, "Expected events ")
          assertThat( events.size() == 3, "Expected 3 events ")
          print( events.toString( ) )
          Date currentTime = new Date( System.currentTimeMillis( ) + TimeUnit.MINUTES.toMillis( 5 ) ) // allow for some clock-skew
          events.get( 0 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 1, "Expected event ID 1, but was: ${eventId}" )
            assertThat( eventType == 'WorkflowExecutionStarted', "Expected event type WorkflowExecutionStarted, but was: ${eventType}" )
            assertThat( workflowExecutionStartedEventAttributes != null, "Expected event attributes" )
            workflowExecutionStartedEventAttributes.with {
              assertThat( taskList != null, "Expected task list")
              assertThat( taskList.name == 'list', "Expected task list 'list', but was: ${taskList.name}" )
              assertThat( workflowType != null, "Expected workflow type" )
              assertThat( workflowType.name == workflowTypeName, "Expected workflow type name ${workflowTypeName}, but was: ${workflowType.name}" )
              assertThat( workflowType.version == '1', "Expected workflow type version 1, but was: ${workflowType.version}" )
              assertThat( executionStartToCloseTimeout == '60', "Expected exec start to close timeout 60, but was: ${executionStartToCloseTimeout}" )
              assertThat( taskStartToCloseTimeout == '60', "Expected stask tart to close timeout 60, but was: ${taskStartToCloseTimeout}" )
              assertThat( parentInitiatedEventId == 0, "Expected parent initiated event id 0, but was: ${parentInitiatedEventId}" )
              assertThat( input == 'input-here', "Expected input input-here, but was: ${input}" )
              assertThat( childPolicy == 'TERMINATE', "Expected child policy TERMINATE, but was: ${childPolicy}" )
              assertThat( tagList == ['tags', 'go', 'here'], "Expected tag list 'tags,go,here', but was: ${tagList}" )
            }
          }
          events.get( 1 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 2, "Expected event ID 2, but was: ${eventId}" )
            assertThat( eventType == 'DecisionTaskScheduled', "Expected event type DecisionTaskScheduled, but was: ${eventType}" )
            assertThat( decisionTaskScheduledEventAttributes != null, "Expected event attributes" )
            decisionTaskScheduledEventAttributes.with {
              assertThat( taskList != null, "Expected task list" )
              assertThat( taskList.name == 'list', "Expected task list 'list', but was: ${taskList.name}" )
              assertThat( startToCloseTimeout == '60', "Expected start to close timeout 60, but was: ${startToCloseTimeout}" )
            }
          }
          events.get( 2 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 3, "Expected event ID 3, but was: ${eventId}" )
            assertThat( eventType == 'DecisionTaskStarted', "Expected event type DecisionTaskStarted, but was: ${eventType}" )
            assertThat( decisionTaskStartedEventAttributes != null, "Expected event attributes" )
            decisionTaskStartedEventAttributes.with {
              assertThat( identity == 'test-decider-1', "Expected identity test-decider-1, but was: ${identity}" )
              assertThat( scheduledEventId == 2, "Expected scheduled event Id 2, but was: ${scheduledEventId}" )
            }
          }
          taskToken
        }

        print( "Responding with schedule activity task" )
        respondDecisionTaskCompleted(new RespondDecisionTaskCompletedRequest(
                taskToken: decisionTaskToken1,
                executionContext: 'foo',
                decisions: [
                        new Decision(
                                decisionType: 'ScheduleActivityTask',
                                scheduleActivityTaskDecisionAttributes: new ScheduleActivityTaskDecisionAttributes(
                                        activityType: new ActivityType( ).withName( activityTypeName ).withVersion( '1' ),
                                        activityId: 'activity-1',
                                        input: 'input',
                                        scheduleToCloseTimeout: '120',
                                        scheduleToStartTimeout: '120',
                                        startToCloseTimeout: '120',
                                        heartbeatTimeout: '120',
                                        taskList: new TaskList( name: 'list' )
                                )
                        )
                ]
        ))

        print( "Polling for activity task ${domainName}/list" )
        String activityTaskToken = pollForActivityTask(new PollForActivityTaskRequest(
                domain: domainName,
                taskList: new TaskList(name: 'list'),
                identity: 'test-activity-processor-1'
        )).with {
          assertThat( taskToken != null, "Expected task token" )
          assertThat( workflowExecution != null, "Expected workflow execution ")
          assertThat( workflowExecution.runId == runId, "Expected workflow execution runId ${runId}, but was: ${workflowExecution.runId}")
          assertThat( workflowExecution.workflowId == workflowId, "Expected workflow execution workflowId ${workflowId}, but was: ${workflowExecution.workflowId}")
          assertThat( activityType != null, "Expected activity type ")
          assertThat( activityType.name == activityTypeName, "Expected activity type name ${activityTypeName}, but was: ${activityType.name}")
          assertThat( activityType.version == '1', "Expected activity type version 1, but was: ${activityType.version}")
          assertThat( activityId == 'activity-1', "Expected activity id activity-1, but was: ${activityId}")
          assertThat( startedEventId == 6, "Expected started event ID 6, but was: ${startedEventId}")
          assertThat( input == 'input', "Expected input input, but was: ${input}")
          taskToken
        }

        print( "Responding activity task completed" )
        respondActivityTaskCompleted(new RespondActivityTaskCompletedRequest(
                taskToken: activityTaskToken,
                result: 'activity-1-result-here'
        ))

        print( "Polling for decision task ${domainName}/list" )
        String decisionTaskToken2 = pollForDecisionTask(new PollForDecisionTaskRequest(
                domain: domainName,
                taskList: new TaskList(name: 'list'),
                identity: 'test-decider-1'
        )).with {
          assertThat( previousStartedEventId == 3, "Expected previous started event ID 3, but was: ${previousStartedEventId}" )
          assertThat( startedEventId == 9, "Expected started event ID 9, but was ${startedEventId}" )
          assertThat( taskToken != null, "Expected task token" )
          assertThat( workflowExecution != null, "Expected workflow execution ")
          assertThat( workflowExecution.runId == runId, "Expected workflow execution runId ${runId}, but was: ${workflowExecution.runId}")
          assertThat( workflowExecution.workflowId == workflowId, "Expected workflow execution workflowId ${workflowId}, but was: ${workflowExecution.workflowId}")
          assertThat( workflowType != null, "Expected workflow type ")
          assertThat( workflowType.name == workflowTypeName, "Expected workflow type name ${workflowTypeName}, but was: ${workflowType.name}")
          assertThat( workflowType.version == '1', "Expected workflow type version 1, but was: ${workflowType.version}")
          assertThat( events != null, "Expected events ")
          print( events.toString( ) )
          assertThat( events.size() == 9, "Expected 9 events")
          Date currentTime = new Date( System.currentTimeMillis( ) + TimeUnit.MINUTES.toMillis( 5 ) ) // allow for some clock-skew
          // events 0-2 validated previously
          events.get( 0 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 1, "Expected event ID 1, but was: ${eventId}" )
            assertThat( eventType == 'WorkflowExecutionStarted', "Expected event type WorkflowExecutionStarted, but was: ${eventType}" )
            assertThat( workflowExecutionStartedEventAttributes != null, "Expected event attributes" )
          }
          events.get( 1 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 2, "Expected event ID 2, but was: ${eventId}" )
            assertThat( eventType == 'DecisionTaskScheduled', "Expected event type DecisionTaskScheduled, but was: ${eventType}" )
            assertThat( decisionTaskScheduledEventAttributes != null, "Expected event attributes" )
          }
          events.get( 2 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 3, "Expected event ID 3, but was: ${eventId}" )
            assertThat( eventType == 'DecisionTaskStarted', "Expected event type DecisionTaskStarted, but was: ${eventType}" )
            assertThat( decisionTaskStartedEventAttributes != null, "Expected event attributes" )
          }
          events.get( 3 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 4, "Expected event ID 4, but was: ${eventId}" )
            assertThat( eventType == 'DecisionTaskCompleted', "Expected event type DecisionTaskStarted, but was: ${eventType}" )
            assertThat( decisionTaskCompletedEventAttributes != null, "Expected event attributes" )
            decisionTaskCompletedEventAttributes.with {
              assertThat( scheduledEventId == 2, "Expected scheduled event Id 2, but was: ${scheduledEventId}" )
              assertThat( startedEventId == 3, "Expected started event Id 3, but was: ${scheduledEventId}" )
              assertThat( executionContext == 'foo', "Expected execution context foo, but was: ${executionContext}" )
            }
          }
          events.get( 4 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 5, "Expected event ID 5, but was: ${eventId}" )
            assertThat( eventType == 'ActivityTaskScheduled', "Expected event type DecisionTaskStarted, but was: ${eventType}" )
            assertThat( activityTaskScheduledEventAttributes != null, "Expected event attributes" )
            activityTaskScheduledEventAttributes.with {
              assertThat( taskList != null, "Expected task list")
              assertThat( taskList.name == 'list', "Expected task list 'list', but was: ${taskList.name}" )
              assertThat( activityType != null, "Expected activity type" )
              assertThat( activityType.name == activityTypeName, "Expected activity type name ${activityTypeName}, but was: ${activityType.name}" )
              assertThat( activityType.version == '1', "Expected activity type version 1, but was: ${activityType.version}" )
              assertThat( activityId == 'activity-1', "Expected activity id activity-1, but was: ${activityId}" )
              assertThat( decisionTaskCompletedEventId == 4, "Expected decision task completed event id 0, but was: ${decisionTaskCompletedEventId}" )
              assertThat( input == 'input', "Expected input input, but was: ${input}" )
              assertThat( scheduleToStartTimeout == '120', "Expected schedule to start timeout 120, but was: ${scheduleToStartTimeout}" )
              assertThat( scheduleToCloseTimeout == '120', "Expected schedule to close timeout 120, but was: ${scheduleToCloseTimeout}" )
              assertThat( startToCloseTimeout == '120', "Expected start to close timeout 120, but was: ${startToCloseTimeout}" )
              assertThat( heartbeatTimeout == '120', "Expected heartbeat timeout 120, but was: ${heartbeatTimeout}" )
            }
          }
          events.get( 5 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 6, "Expected event ID 6, but was: ${eventId}" )
            assertThat( eventType == 'ActivityTaskStarted', "Expected event type DecisionTaskStarted, but was: ${eventType}" )
            assertThat( activityTaskStartedEventAttributes != null, "Expected event attributes" )
            activityTaskStartedEventAttributes.with {
              assertThat( identity == 'test-activity-processor-1', "Expected identity test-activity-processor-1, but was: ${identity}" )
              assertThat( scheduledEventId == 5, "Expected scheduled event Id 5, but was: ${scheduledEventId}" )
            }
          }
          events.get( 6 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 7, "Expected event ID 7, but was: ${eventId}" )
            assertThat( eventType == 'ActivityTaskCompleted', "Expected event type DecisionTaskStarted, but was: ${eventType}" )
            assertThat( activityTaskCompletedEventAttributes != null, "Expected event attributes" )
            activityTaskCompletedEventAttributes.with {
              assertThat( result == 'activity-1-result-here', "Expected result activity-1-result-here, but was: ${result}" )
              assertThat( scheduledEventId == 5, "Expected scheduled event Id 5, but was: ${scheduledEventId}" )
              assertThat( startedEventId == 6, "Expected started event Id 6, but was: ${scheduledEventId}" )
            }
          }
          events.get( 7 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 8, "Expected event ID 8, but was: ${eventId}" )
            assertThat( eventType == 'DecisionTaskScheduled', "Expected event type DecisionTaskStarted, but was: ${eventType}" )
            assertThat( decisionTaskScheduledEventAttributes != null, "Expected event attributes" )
            decisionTaskScheduledEventAttributes.with {
              assertThat( taskList != null, "Expected task list" )
              assertThat( taskList.name == 'list', "Expected task list 'list', but was: ${taskList.name}" )
              assertThat( startToCloseTimeout == '60', "Expected start to close timeout 60, but was: ${startToCloseTimeout}" )
            }
          }
          events.get( 8 ).with {
            assertThat( currentTime.after( eventTimestamp ), "Expected event time in past" )
            assertThat( eventId == 9, "Expected event ID 9, but was: ${eventId}" )
            assertThat( eventType == 'DecisionTaskStarted', "Expected event type DecisionTaskStarted, but was: ${eventType}" )
            assertThat( decisionTaskStartedEventAttributes != null, "Expected event attributes" )
            decisionTaskStartedEventAttributes.with {
              assertThat( identity == 'test-decider-1', "Expected identity test-decider-1, but was: ${identity}" )
              assertThat( scheduledEventId == 8, "Expected scheduled event Id 8, but was: ${scheduledEventId}" )
            }
          }
          taskToken
        }

        print( "Responding workflow complete" );
        respondDecisionTaskCompleted(new RespondDecisionTaskCompletedRequest(
                taskToken: decisionTaskToken2,
                decisions: [
                        new Decision( )
                                .withDecisionType( "CompleteWorkflowExecution" )
                                .withCompleteWorkflowExecutionDecisionAttributes( new CompleteWorkflowExecutionDecisionAttributes( )
                                .withResult( "42" )
                        )
                ]
        ))

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
