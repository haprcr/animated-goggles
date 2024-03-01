import json
import logging
from google import pubsub_v1
from google.cloud import monitoring_v3
import google.api_core.exceptions as gcp_exceptions
from google.cloud import logging as cloud_logging


# Access the Config file
with open("alert_config.json", "r") as alert_config:
        alert_config = json.load(alert_config)

logging_client = cloud_logging.Client()
logging_client.setup_logging()

log_name = alert_config["Log_Group"]
custom_logger = logging.getLogger(log_name)


def create_alerting_policy(alert_info, project_id):
    try:
            custom_logger.info("Creating the Alert Policy Client")
            policy_client = monitoring_v3.AlertPolicyServiceClient()


            custom_logger.info("Loading the Alert Policy json object")
            policy = monitoring_v3.AlertPolicy.from_json(alert_info, ignore_unknown_fields=True)

            project_name = f"projects/{project_id}"

            
            custom_logger.info("Initialising the Create Alert Policy Request with the required arguments")
            Alert_Policy_Request = monitoring_v3.CreateAlertPolicyRequest(name = project_name)

            Alert_Policy_Request.alert_policy = policy

            custom_logger.info("Calling the method to create the Alering policy")

            create_policy_request = policy_client.create_alert_policy(request=Alert_Policy_Request)

            custom_logger.info("Response from the client is: ")
            custom_logger.info(create_policy_request)
            return True
    except ValueError as val_err:
        custom_logger.error("ValueError in create_alerting_policy(): %s", val_err, exc_info=True)
        return False
    except Exception as err:
        custom_logger.error("Error in create_alerting_policy(): %s", err, exc_info=True)
        return False



def create_channel(topic_id, project_id):
    try:
        custom_logger.info("Creating the Monitoring Notification Channel Client")
        channel_client = monitoring_v3.NotificationChannelServiceClient()

        custom_logger.info("Initialising the Notification Channel with the required arguments")
        notification_channel = monitoring_v3.NotificationChannel(
            type="pubsub", 
            display_name="Spanner Metric Alerts Notification Channel", 
            enabled=True
        )
        notification_channel.labels["topic"] = topic_id
       

        project_name = f"projects/{project_id}"
        custom_logger.info("Creating the Notification Channel Request object")
        channel_request = monitoring_v3.CreateNotificationChannelRequest(
            name = project_name,
            notification_channel = notification_channel
        )

        
        custom_logger.info("Creating the request to  create a Notification Channel")
        channel_response = channel_client.create_notification_channel(
            request=channel_request
        )

        custom_logger.info("Response received from the client")
        custom_logger.info(f"Notification channel {channel_response.name} created.")

        return True, channel_response.name
    except gcp_exceptions.InvalidArgument as err:
        custom_logger.error("InvalidArgument Error in create_channel(): %s", err, exc_info=True)
        return False, err
    except Exception as err:
        err_msg = f"Error while creating the Notification Channel in create_channel(): {err}"
        custom_logger.error(err_msg)
        return False, err_msg



# def create_pubsub(topic_id):
def create_pubsub(topic_name, project_id):
    try:
        custom_logger.info("Creating a Pub/Sub Client")
        pubsub_client = pubsub_v1.PublisherClient()

        custom_logger.info("Creating the fully qualified topic name")
        topic_id = pubsub_client.topic_path(project_id, topic_name)
        
        custom_logger.info("Fully qualified topic name is: ", topic_id)

        custom_logger.info("Initializing Topic object with the required parameters")
        topic_req = pubsub_v1.Topic()
        topic_req.name = topic_id


        custom_logger.info("Sending a request to Pub/Sub client to create the topic")
        pubsub_response = pubsub_client.create_topic(topic_req)
        custom_logger.info("Response from Pub/Sub Client is: ", pubsub_response)
        custom_logger.info(f"Pub/Sub topic created: ", topic_name)
        return True, topic_id


    except gcp_exceptions.AlreadyExists as err:
        err_msg = f"Error while creating the Pub/Sub topic: {err}"
        custom_logger.error(err_msg)
        custom_logger.error(f"The topic already exists: {topic_id}")
        return False, err_msg




def main(request):
    try:
        custom_logger.info("Accessing Project Id from the config file.")
        project_id = alert_config["Project_Id"]


        custom_logger.info("Accessing Topic Name from the config file.")
        topic_name = alert_config["Topic_Name"]

        # topic_id = f"projects/{project_id}/topics/{topic_name}"
        custom_logger.info("Calling the function to create the Pub/Sub Topic")
        status_1, response_msg_1 = create_pubsub(topic_name, project_id)

        if status_1:
            custom_logger.info("Pub/Sub topic created successfully.")
            custom_logger.info("Calling the function to create a notification channel")

            status_2, response_msg_2 = create_channel(response_msg_1, project_id)

            if status_2:
                custom_logger.info(f"Notification Channel {response_msg_2} linked to topic {response_msg_1} is created successfully.")

                notification_channel_id = response_msg_2

                custom_logger.info("Loading Alert Configurations from the file.")
                with open("alert_configurations.json", "rt") as alert_configurations:
                    alert_configurations = json.load(alert_configurations)
                    for alert_info in alert_configurations:

                        # Add the created notification channel object

                        alert_info["notificationChannels"] = [notification_channel_id]

                        # Add notificationChannelStrategy to the alert policy json object

                        notificationChannelStrategy = [
                                {
                                "notificationChannelNames": [
                                    notification_channel_id # Resource name for the notification channel
                                ],
                                "renotifyInterval": "2700s" # The frequency at which to send reminder notifications for open incidents.
                                }
                        ]
                        alert_info["alertStrategy"]["notificationChannelStrategy"] = notificationChannelStrategy

                        # Convert the object to a JSON formatted string
                        alert_info = json.dumps(alert_info)
                        custom_logger.info("Updated the required Alerting policy parameters")
                        custom_logger.info("Calling the function to create the Alerting policy")
                        status_3 = create_alerting_policy(alert_info, project_id)

                        # Check the Status of the execution
                        if status_3 == False:
                            raise Exception("Error in the creation of Alerting Policy. create_alerting_policy() function returned False")
                        
                        success_msg = f"Alerting policy is created successfully"
                        custom_logger.info(success_msg)
                        return "OK"
            else:
                raise Exception(response_msg_2)
        else:
            raise Exception(response_msg_1)

    except Exception as err:
        custom_logger.error("An error occurred: %s", err)



