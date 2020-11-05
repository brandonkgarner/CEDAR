# This code is used to create Ansible files for deploying Lambda's
# all that is needed is a target Lambda, tests, and it will do the rest.
# finds associate roles and policies
# creates Ansible modules based on those policies and roles
# defines the Lambdas and creates them with tests
# finds api-gateways or other events
# if api found defines the security needed. creates modules for deployment with templates
import re
from time import sleep
import os
import time
import random
import shutil
from datetime import datetime, date
import boto3
from botocore.exceptions import ClientError
import json
import sys
from shutil import copyfile
import fileinput
import logging
import urllib

import distutils
from distutils import dir_util

import awsconnect

from awsconnect import awsConnect

#from context import FormatContext
#import pyaml
# pip install pyyaml
from microUtils import writeYaml, writeJSON, account_replace, loadNetworkMap, loadConfig, ansibleSetup, serviceID
from microFront import CloudFrontMolder
# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
dir_path = os.path.dirname(__file__)


class FileCopier():
    origin = None

    temp = None

    def __init__(self):
        pass

    def readPermissions(self, target, aconnect):
        #client = boto3.client('lambda')
        client = aconnect.__get_client__('s3')
        s3 = aconnect.__get_resource__('s3')
        bucket_name = 'cr-portal-dev'
        b_acl = s3.BucketAcl(bucket_name)

        acl = b_acl.grants
        print(acl)
        print("  ----   COMPLETE ---  ")

    def resetPermissions(self, target, aconnect):
        #client = boto3.client('lambda')
        client = aconnect.__get_client__('s3')
        s3 = aconnect.__get_resource__('s3')
        bucket_name = 'cr-backup-db'
        b_acl = s3.BucketAcl(bucket_name)
        policy = s3.BucketPolicy(bucket_name)

        file_acl = "s3_ACL.json"
        with open(file_acl, 'r') as aclfile:
            jacl = json.load(aclfile)
        print(jacl)
        b_acl.put(AccessControlPolicy=jacl)
        print(" -- -->  policy ACL updated")
        policy.delete()
        print(" -- -->  policy deleted")
        file = 's3_Policy.json'
        with open(file, 'r') as policyfile:
            jdata = json.load(policyfile)
        response = policy.put(ConfirmRemoveSelfBucketAccess=True, Policy=jdata)
        print(" -- -->  policy updated")
        print(response)


# aws s3api put-bucket-acl --bucket MyBucket --grant-full-control emailaddress=user1@example.com,emailaddress=user2@example.com --grant-read uri=http://acs.amazonaws.com/groups/global/AllUsers
# aws s3api delete-bucket-policy --bucket  cr-portal-dev
#  aws rds add-role-to-db-cluster --db-cluster-identifier some-cluster-id --role-arn arn:aws:iam::1234567890:role/S3_ROLE
if __name__ == "__main__":
    found = None
    length = 0
    config = "ENVR.yaml"
    fullpath = "%s/%s" % (dir_path, config)
    origin, global_accts = loadConfig(fullpath, 'dev')
    eID = 1001000100001
    if 'eID' in origin:
        eID = origin['eID']
    if 'services_map' in origin:
        mapfile = origin['services_map']
        eID = serviceID(origin['account'], mapfile, origin['all'])

    print("  ..... INIT..... 0002")
    accID = origin['account']
    region = 'us-east-1'
    awsconnect.stsClient_init()
    sts_client = awsconnect.stsClient
    aconnect = awsConnect(
        accID, eID, origin['role_definer'], sts_client, region)
    aconnect.connect()

    fc = FileCopier()
    fc.resetPermissions(file, aconnect)
    # fc.removePermissions(file,aconnect)
