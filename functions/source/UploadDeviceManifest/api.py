"""API Handler for ConnectSense Developer Kit."""
import os
import json
import logging
import boto3
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from manifest import ManifestItem
from manifest import ManifestIterator

iot = boto3.client("iot")

POLICY_NAME = os.environ["DEVICE_POLICY"]


class ManifestImportException(Exception):
    """Manifest Named Exception."""


def load_verify_cert_by_file(filename):
    """Load the verification certificate that will be used to verify manifest
    entries."""
    with open(filename, "rb") as buf:
        verification_cert = buf.read()
    return verification_cert


def _make_thing(device_id, certificate_arn):
    """Creates an AWS-IOT "thing" and attaches the certificate."""
    try:
        response = iot.create_thing(thingName=device_id)
        thing_arn = response["thingArn"]
    except:
        raise ManifestImportException("Unable to create thing")

    try:
        response = iot.attach_thing_principal(
            thingName=device_id, principal=certificate_arn
        )
    except:
        raise ManifestImportException("Unable to attach certificate to thing")

    return thing_arn


def _import_certificate(certificate_x509_pem, policy_name):
    """Attach policy to imported certificate."""
    response = iot.register_certificate_without_ca(certificatePem=certificate_x509_pem)

    iot.attach_policy(policyName=policy_name, target=response["certificateArn"])

    iot.update_certificate(certificateId=response["certificateId"], newStatus="ACTIVE")

    return response["certificateArn"]


def _invoke_import_manifest(policy_name, manifest, cert_pem):
    """Processes a manifest and loads entries into AWS-IOT."""

    verification_cert = x509.load_pem_x509_certificate(
        data=cert_pem, backend=default_backend()
    )

    iterator = ManifestIterator(manifest)

    # this should only contain one manifest item
    things = []
    while iterator.index != 0:
        manifest_item = ManifestItem(next(iterator), verification_cert)

        certificate_arn = _import_certificate(
            manifest_item.get_certificate_chain(), policy_name
        )

        thing_name = "CS-CORD-DK-" + manifest_item.identifier
        thing_arn = _make_thing(thing_name, certificate_arn)

        if thing_arn:
            things.append(thing_name)

    return things


def upload_manifest(event, context):
    print(event)
    """Create the DevKit Thing, Policy, and Certificates."""
    try:
        cert = load_verify_cert_by_file("./MCHP_manifest_signer.crt")
        manifest = json.loads(event["body"])
        print(manifest)

        _invoke_import_manifest(POLICY_NAME, manifest, cert)

        return {"statusCode": 200, "body": json.dumps({"success": True})}

    except ManifestImportException as error:
        print(error)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "type": type(error).__name__,
                    "error": error,
                }
            ),
        }
