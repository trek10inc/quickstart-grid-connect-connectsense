"""Temperature threshold excess handler."""
import os
import logging
import boto3

logger = logging.getLogger("lambda_logger")
logger.setLevel(logging.DEBUG)
sns = boto3.client("sns")  # type: botostubs.SNS


def process_alerts(event, context):
    """Surface and publish device telemetry."""
    logger.debug(event)

    sns.publish(
        Subject="Watts threshold excess",
        Message="The wattage recorded for device with serial {0} is {1}".format(
            event["serial"], event["watts"]
        ),
        TopicArn=os.environ["TOPIC_ARN"],
    )

    return {"statusCode": 200}
