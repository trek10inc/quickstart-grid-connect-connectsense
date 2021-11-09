import os
import logging
import boto3
import time

logger = logging.Logger(__name__)
glue_client = boto3.client("glue")
JOB_NAME = os.environ.get("JOB_NAME")
CRAWLER_NAME = os.environ.get("CRAWLER_NAME")
CRAWL_TIMEOUT = 800
CRAWL_WAIT_INTERVAL = 30


def handler(event, context):
    logger.debug("Starting Crawler")
    glue_client.start_crawler(Name=CRAWLER_NAME)
    elapsed_time = 0
    crawler_status = None
    crawler_succeeded = False
    while not crawler_status != "running" and elapsed_time < CRAWL_TIMEOUT:
        time.sleep(CRAWL_WAIT_INTERVAL)
        response = glue_client.get_crawler(Name=CRAWLER_NAME)
        crawler_status = response["State"].lower()
        elapsed_time += CRAWL_WAIT_INTERVAL
        if (
            crawler_status == "ready"
            and response["LastCrawl"]["Status"].lower() == "succeeded"
        ):
            crawler_succeeded = True

    if crawler_succeeded:
        response = glue_client.start_job_run(JobName=JOB_NAME)
    else:
        logger.debug("Crawler did not succeeed")
