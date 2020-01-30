import boto3
import json
import sys
import os
from colorama import Fore, Back, Style

with open('test_cases.json', 'r') as file:
    test_cases = json.load(file)

    # create test file
    test_file_name = "test_file"
    test_file = open(test_file_name, "w+")
    test_file.write("Test sample\r\n")

    buckets = test_cases['buckets']
    resources = test_cases['resources']
    default_expected_permissions = test_cases['default_expected_permissions']
    iams = test_cases['iams']

    for iam, iam_infos in iams.items():
        print("{}### Testing IAM {} ###{}".format(Style.BRIGHT, iam, Style.NORMAL))
        print("{}Setting up IAM S3 client ...{}".format(Style.DIM, Style.NORMAL))
        s3_client = boto3.client(
            's3',
            region_name='eu-west-1',
            aws_access_key_id=iam_infos['key'],
            aws_secret_access_key=iam_infos['secret']
        )

        for bucket in buckets:
            print("Testing against bucket '{}'".format(bucket))
            if 'resources' in iam_infos and hasattr(iam_infos, 'items'):
                for resource, resource_infos in iam_infos['resources'].items():
                    print("  - Testing resource '{}' of type {}".format(resource, resource_infos['type']))

                    # use default actions permissions
                    tmp_actions = default_expected_permissions.copy()

                    # if bucket is allowed, update permissions with IAM's ones
                    if bucket in iam_infos['allowed_buckets']:
                        print("  - Using custom expected permissions")
                        if 'actions' in resource_infos and hasattr(resource_infos['actions'], 'items'):
                            for action, expected_result in resource_infos['actions'].items():
                                tmp_actions[action] = expected_result
                    else:
                        print("  - Using default expected permissions")

                    if hasattr(tmp_actions, 'items'):
                        for action, expected_result in tmp_actions.items():
                            print("    - Expect action '{}' on resource '{}' to be {}{}{}".format(
                                action,
                                resource,
                                Style.BRIGHT,
                                'ALLOWED' if expected_result is True else 'NOT ALLOWED',
                                Style.NORMAL
                            ))
                            if resource_infos['type'] == "folder":
                                test_file_path = resource + "/" + test_file_name
                            else:
                                test_file_path = resource
                            test_result = False
                            error_msg = ""

                            # handles ListBucket
                            if action == 'ListBucket':
                                try:
                                    s3_client.list_objects(
                                        Bucket=bucket
                                    )
                                    test_result = True
                                except Exception as e:
                                    error_msg = "{}{} ({}){}".format(
                                        Fore.RED,
                                        e,
                                        sys.exc_info()[0],
                                        Fore.RESET)
                            # handles PutObject
                            if action == 'PutObject':
                                try:
                                    s3_client.put_object(
                                        Bucket=bucket,
                                        Key=test_file_path,
                                        Body=test_file_path
                                    )
                                    test_result = True
                                except Exception as e:
                                    error_msg = "{}{} ({} - {}){}".format(
                                        Fore.RED,
                                        e,
                                        test_file_path,
                                        sys.exc_info()[0],
                                        Fore.RESET)
                            # handles GetObject
                            if action == 'GetObject':
                                try:
                                    s3_client.get_object(
                                        Bucket=bucket,
                                        Key=test_file_path
                                    )
                                    test_result = True
                                except Exception as e:
                                    error_msg = "{}{} ({} - {}){}".format(
                                        Fore.RED,
                                        e,
                                        test_file_path,
                                        sys.exc_info()[0],
                                        Fore.RESET)

                            # handles MultipartUpload
                            if action == 'MultipartUpload':
                                try:
                                    MU = s3_client.create_multipart_upload(
                                        Bucket=bucket,
                                        Key=test_file_path
                                    )

                                    if 'UploadId' not in MU:
                                        error_msg = "No UploadId received from S3"
                                    else:
                                        part = s3_client.upload_part(
                                            Bucket=bucket,
                                            Key=test_file_path,
                                            PartNumber=1,
                                            UploadId=MU['UploadId']
                                        )

                                        s3_client.complete_multipart_upload(
                                            Bucket=bucket,
                                            Key=test_file_path,
                                            MultipartUpload={
                                                'Parts': [
                                                    {
                                                        'ETag': part['ETag'],
                                                        'PartNumber': 1
                                                    },
                                                ]
                                            },
                                            UploadId=MU['UploadId']
                                        )
                                        test_result = True

                                except Exception as e:
                                    error_msg = "{}{} ({} - {}){}".format(
                                        Fore.RED,
                                        e,
                                        test_file_path,
                                        sys.exc_info()[0],
                                        Fore.RESET)

                            # handles AbortMultipartUpload
                            if action == 'AbortMultipartUpload':
                                try:
                                    MU = s3_client.create_multipart_upload(
                                        Bucket=bucket,
                                        Key=test_file_path
                                    )

                                    if 'UploadId' not in MU:
                                        error_msg = "No UploadId received from S3"
                                    else:
                                        s3_client.abort_multipart_upload(
                                            Bucket=bucket,
                                            Key=test_file_path,
                                            UploadId=MU['UploadId']
                                        )
                                        test_result = True

                                except Exception as e:
                                    error_msg = "{}{} ({} - {}){}".format(
                                        Fore.RED,
                                        e,
                                        test_file_path,
                                        sys.exc_info()[0],
                                        Fore.RESET)

                            color = Fore.GREEN if test_result == expected_result else Fore.RED
                            result = "OK" if test_result == expected_result else "KO, {}{}{} expected".format(
                                Style.BRIGHT,
                                expected_result,
                                Style.NORMAL
                            )
                            if test_result != expected_result and error_msg is not "":
                                result = "{} : {}".format(result, error_msg)
                            print(color + "        => {}".format(result) + Style.RESET_ALL)
                    else:
                        print("No 'actions' index found on '{}' resource, or wrong object type (Dict needed)".format(resource))
            else:
                print("No 'resources' index found on '{}' IAM, or wrong object type (Dict needed)".format(iam))

    # Delete test file
    test_file.close()
    if os.path.exists(test_file_name):
        os.remove(test_file_name)

    # test report
