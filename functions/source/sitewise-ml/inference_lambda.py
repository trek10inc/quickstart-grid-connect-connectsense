import os
import boto3
import json
import io
import csv
import logging

logger = logging.Logger(__name__)

PARAM_NAME = os.environ["PARAM_NAME"]
TOPIC_ARN = os.environ["TOPIC_ARN"]

sagemaker_runtime_client = boto3.client("runtime.sagemaker")
sagemaker_client = boto3.client("sagemaker")
ssm_client = boto3.client("ssm")
sns_client = boto3.client("sns")
s3_client = boto3.client("s3")

threshold = float(ssm_client.get_parameter(Name=PARAM_NAME)["Parameter"]["Value"])
endpoint_name = None
existing_endpoints = sagemaker_client.list_endpoints()["Endpoints"]
for e in existing_endpoints:
    if e["EndpointName"].startswith("randomcutforest"):
        endpoint_name = e["EndpointName"]
        break


def handler(event, context):
    volts = []
    amps = []
    watts = []
    power_factor = []
    watt_hours = []
    timestamps = []
    asset_ids = []
    for record in event["Records"]:
        file_bucket = record["s3"]["bucket"]["name"]
        file_key = record["s3"]["object"]["key"]
        data_list = (
            s3_client.get_object(Bucket=file_bucket, Key=file_key)["Body"]
            .read()
            .decode("utf-8")
        )
        data_list = data_list.replace("}{", "},{")
        data_list = data_list.rstrip(",")
        data_list = "[" + data_list
        data_list = data_list + "]"
        data_list = json.loads(data_list)
        for data in data_list:
            logger.debug(data)
            property_name = data["name"]
            asset_id = data["asset_id"]
            asset_ids.append(asset_id)
            values = data["values"]
            for v in values:
                packet = {
                    property_name: v["value"],
                    "timestamp": v["timestamp"],
                    "asset_id": asset_id,
                }
                timestamps.append(v["timestamp"])
                if property_name.lower() == "volts":
                    volts.append(packet)
                elif property_name.lower() == "watts":
                    watts.append(packet)
                elif property_name.lower() == "amps":
                    amps.append(packet)
                elif property_name.lower() == "watt_hours":
                    watt_hours.append(packet)
                elif property_name.lower() == "power_factor":
                    power_factor.append(packet)

        timestamps = list(set(timestamps))
        asset_ids = list(set(asset_ids))
        for asset in asset_ids:
            final_list = []
            for t in timestamps:
                packet = {"timestamp": t}
                for v in volts:
                    if v["timestamp"] == t and v["asset_id"] == asset:
                        packet.update({"volts": v["volts"]})
                        break
                for v in amps:
                    if v["timestamp"] == t and v["asset_id"] == asset:
                        packet.update({"amps": v["amps"]})
                        break
                for v in watts:
                    if v["timestamp"] == t and v["asset_id"] == asset:
                        packet.update({"watts": v["watts"]})
                        break
                for v in power_factor:
                    if v["timestamp"] == t and v["asset_id"] == asset:
                        packet.update({"power_factor": v["power_factor"]})
                        break
                for v in watt_hours:
                    if v["timestamp"] == t and v["asset_id"] == asset:
                        packet.update({"watt_hours": v["watt_hours"]})
                        break
                try:
                    packet.pop("timestamp")
                    assert len(packet.keys()) == 5
                    final_list.append(packet)
                except AssertionError:
                    logger.debug("Packet missing data: {}".format(packet))
                    pass

            keys = final_list[0].keys()
            csv_file = io.StringIO()
            dict_writer = csv.DictWriter(csv_file, keys)
            dict_writer.writerows(final_list)
            csv_payload = csv_file.getvalue()

            response = sagemaker_runtime_client.invoke_endpoint(
                EndpointName=endpoint_name, Body=csv_payload, ContentType="text/csv"
            )
            body = json.loads(response["Body"].read().decode("utf-8"))
            scores = body["scores"]
            for score in scores:
                prediction = score["score"]
                if float(prediction) >= threshold:
                    message = "Failure predicted on asset {}. Please perform maintenance".format(
                        asset
                    )
                    subject = "Future Failure Possible - Action Required"
                    logger.debug(message)
                    sns_client.publish(
                        TopicArn=TOPIC_ARN, Message=message, Subject=subject
                    )
                    break
                else:
                    pass
