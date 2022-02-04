import os
import json
import boto3
import datetime
import base64
import logging

session = boto3.session.Session()
logger = logging.Logger(__name__)

sitewise_client = boto3.client("iotsitewise")
asset_model_info = sitewise_client.describe_asset_model(
    assetModelId=os.environ["ASSET_MODEL_ID"]
)

asset_model_properties = asset_model_info["assetModelProperties"]


def transformDateTimeFormat(in_ts):
    date_obj = datetime.datetime.fromtimestamp(in_ts)
    new_format = date_obj.strftime("%Y%m%d%H%M%S")
    return new_format


def handler(event, context):

    output = []
    for record in event["records"]:
        record_data = json.loads(base64.b64decode(record["data"]))
        payload = record_data["payload"]
        property_id = payload["propertyId"]
        asset_id = payload["assetId"]
        property_name = None
        property_type = None

        for prop in asset_model_properties:
            if prop["id"] == property_id:
                property_name = prop["name"]
                property_type = prop["dataType"]
                break

        output_record_data = {
            "name": property_name,
            "property_id": property_id,
            "property_type": property_type,
            "asset_id": asset_id,
            "values": [],
        }

        for value in record_data["payload"]["values"]:
            record_timestamp = value["timestamp"]["timeInSeconds"]
            record_quality = value["quality"]
            value_key = "{}Value".format(property_type.lower())
            record_value = value["value"][value_key]
            output_record_data["values"].append(
                {
                    "timestamp": transformDateTimeFormat(record_timestamp),
                    "quality": record_quality,
                    "value": record_value,
                }
            )

        for accrued_value in output_record_data["values"]:
            if property_type == "INTEGER" or property_type == "DOUBLE":
                try:
                    assert float(accrued_value["value"]) >= 0
                except AssertionError or TypeError:

                    output_record_data["values"].remove(accrued_value)

        output_record = {
            "recordId": record["recordId"],
            "result": "Ok",
            "data": base64.b64encode(
                json.dumps(output_record_data).encode("utf-8")
            ).decode("utf-8"),
        }
        output.append(output_record)

    return {"records": output}
