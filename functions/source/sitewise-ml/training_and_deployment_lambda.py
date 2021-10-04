import os
import boto3
import pandas as pd
import sagemaker
from sagemaker import RandomCutForest


ROLE_ARN = os.getenv("ROLE_ARN")
INPUT_DATA_PREFIX = "combined"
MODEL_OUTPUT_PREFIX = os.getenv("MODEL_OUTPUT_PREFIX")
SAMPLES_PER_TREE = 5
NUM_OF_TREES = 50
INSTANCE_TYPE = "ml.c5.xlarge"
INSTANCE_COUNT = 1
INFERENCE_INSTANCE = "ml.t2.medium"
INFERENCE_INSTANCE_COUNT = 1

s3_client = boto3.client("s3")
sagemaker_client = boto3.client("sagemaker")


def handler(event, context):
    file_name = event["Records"][0]["s3"]["object"]["key"]
    s3_bucket = event["Records"][0]["s3"]["bucket"]["name"]
    training_data = input_data(file_name, s3_bucket)
    inference_endpoint = create_model(training_data, s3_bucket)
    return inference_endpoint


def create_model(training_data, s3_bucket):
    session = sagemaker.Session()
    endpoints = sagemaker_client.list_endpoints()['Endpoints']
    endpoint_exists = False
    existing_endpoint_name = ""
    for e in endpoints:
        if e['EndpointName'].startswith("randomcutforest"):
            existing_endpoint_name = e['EndpointName']
            endpoint_exists = True
            break
    rcf = RandomCutForest(
        role=ROLE_ARN,
        instance_count=INSTANCE_COUNT,
        instance_type=INSTANCE_TYPE,
        data_location="s3://{}/{}/".format(s3_bucket, INPUT_DATA_PREFIX),
        output_path="s3://{}/{}/output".format(s3_bucket, MODEL_OUTPUT_PREFIX),
        num_samples_per_tree=SAMPLES_PER_TREE,
        num_trees=NUM_OF_TREES,
    )
    numpy_data = training_data.to_numpy()
    record_set = rcf.record_set(numpy_data, channel="train",
                                encrypt=False)
    rcf.fit(record_set)
    if endpoint_exists:
        response = update_model(rcf, existing_endpoint_name)
    else:
        response = deploy_model(rcf)
    return response


def deploy_model(rcf):
    rcf_inference = rcf.deploy(
        initial_instance_count=INFERENCE_INSTANCE_COUNT,
        instance_type=INFERENCE_INSTANCE,
        wait=False
    )
    endpoints = sagemaker_client.list_endpoints()
    endpoint_exists = False
    existing_endpoint_name = ""
    for e in endpoints:
        if e['EndpointName'].startswith("randomcutforest"):
            existing_endpoint_name = e['EndpointName']
            endpoint_exists = True
            break

    return rcf_inference

def update_model(rcf, endpoint_name):
    rcf_inference = rcf.deploy(
        initial_instance_count=INFERENCE_INSTANCE_COUNT,
        instance_type=INFERENCE_INSTANCE,
        wait=False,
        update_endpoint=True,
        endpoint_name=endpoint_name
    )
    return rcf_inference

def input_data(file_name, s3_bucket):
    file_object_data = s3_client.get_object(Bucket=s3_bucket, Key=file_name)

    train_data = pd.read_csv(
        file_object_data["Body"], parse_dates=["timestamp"], delimiter=","
    ).set_index("timestamp")
    return train_data
