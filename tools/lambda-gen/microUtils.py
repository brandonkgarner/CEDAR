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
import yaml
import decimal
# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
dir_path = os.path.dirname(__file__)


class FormatSafeDumper(yaml.SafeDumper):
    def represent_decimal(self, data):
        return self.represent_scalar('tag:yaml.org,2002:str', str(data))

    def represent_set(self, data):
        return self.represent_sequence('tag:yaml.org,2002:seq', list(data))


FormatSafeDumper.add_representer(decimal.Decimal, FormatSafeDumper.represent_decimal)
FormatSafeDumper.add_representer(set, FormatSafeDumper.represent_set)
FormatSafeDumper.add_representer(tuple, FormatSafeDumper.represent_set)


class CommonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (tuple, set)):
            return list(o)
        if isinstance(o, Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)

        if isinstance(o, datetime):
            serial = o.isoformat()
            return serial
        return super(CommonEncoder, self).default(o)


def ansibleSetup(temp, target, isFullUpdate, skipFiles=False):
    ansible_folders = ["defaults", "files", "handlers", "tasks", "templates"]
    rootFolder = temp
    if not skipFiles:
        rootFolder = "%s/%s" % (temp, target)
        if os.path.exists(rootFolder) and isFullUpdate:
            oldDIR = "%s_old" % rootFolder
            if os.path.exists(oldDIR):
                print ("[W] deleting old directory %s " % oldDIR)
                shutil.rmtree(oldDIR)
            os.rename(rootFolder, oldDIR)
            print (rootFolder)
        # folders needed

        if not os.path.exists(rootFolder):
            os.makedirs(rootFolder)
        for folder in ansible_folders:
            newFolder = "%s/%s" % (rootFolder, folder)
            if not os.path.exists(newFolder):
                os.makedirs(newFolder)

        # CREATE Template TASkS
    targetLabel = target.replace("-", "_")
    targetLabel = targetLabel.replace("*", "_")
    taskMain = [{"name": "INITIAL PROJECT SETUP  project VAR", "set_fact": {"project": "{{ %s }}" % targetLabel}}
                ]
    if not skipFiles:
        taskWithFiles = [
            {"import_tasks": "../aws/sts.yml", "vars": {"project": '{{ project }}'}},
            {"import_tasks": "../aws/IAM.yml", "vars": {"project": '{{ project }}'}},
            {"import_tasks": "../aws/lambda.yml", "vars": {"project": '{{ project }}'}}
            # {"include": "dynamo_fixtures.yml project={{ project }}"},
        ]
        taskMain = taskMain + taskWithFiles

    return taskMain, rootFolder, targetLabel


def describe_role(name, aconnect, acct, apiTRigger=False):
    client = aconnect.__get_client__('iam')
    #client = boto3.client('iam')
    if "/" in name:
        name = name.split("/")[1]
    # print(name)
    #print(". oo kkk  ooo k kok")
    roleData = client.get_role(RoleName=name)['Role']
    del roleData['CreateDate']
    arn = roleData['Arn']
    roles = []
    aplcy = client.list_attached_role_policies(RoleName=name)
    policies = []
    givenPolicies = aplcy['AttachedPolicies']
    if apiTRigger:
        print (" #########################################################")
        print (" ########### ADDING Policy : CR-Lambda-APIGW. ############")
        print (" #########################################################")

        pname = "CR-Lambda-APIGW"
        p_arn = "arn:aws:iam::%s:policy/%s" % (acct, pname)
        pDefinition = describe_policy(p_arn, pname, aconnect)
        policies.append(pDefinition)
    if len(givenPolicies) != 0:
        for plcy in givenPolicies:
            polName = plcy['PolicyName']
            polARN = plcy['PolicyArn']
            pDefinition = describe_policy(polARN, polName, aconnect)
            policies.append(pDefinition)
    roles.append({'name': name, 'data': roleData, 'policies': policies})
    return roles, arn


def describe_policy(arn, name, aconnect):
    client = aconnect.__get_client__('iam')
    #client = boto3.client('iam')
    polMeta = client.get_policy(PolicyArn=arn)['Policy']
    polDefined = client.get_policy_version(PolicyArn=arn, VersionId=polMeta['DefaultVersionId'])
    #polDefined = client.get_role_policy(RoleName=name,PolicyName=polName)
    print(" POLICY. %s...." % name)
    print (polDefined)
    doc = polDefined['PolicyVersion']['Document']
    # print("------==polMeta=--------")
    # print (polMeta)
    description = 'CR-Default no description found'
    if 'Description'in polMeta:
        description = polMeta['Description']
    path = polMeta['Path']
    print ("  -->" + path)
    return {'PolicyName': name,
            'Path': path,
            'PolicyDocument': doc,
            'Description': description}


def writeYaml(data, filepath, option=''):
    dd = {"---": data}
    fullpath = '%s%s.%s' % (filepath, option, 'yaml')
    with open(fullpath, 'wb') as outfile:
        yaml.dump(dd, outfile, default_flow_style=False, encoding='utf-8', allow_unicode=True, Dumper=FormatSafeDumper)
    for line in fileinput.input([fullpath], inplace=True):
        if line.strip().startswith("'---"):
            line = '---\n'
        sys.stdout.write(line)
    return fullpath.rsplit("/", 1)[1]


def writeJSON(data, filepath, option=''):
    fullpath = '%s%s.%s' % (filepath, option, 'js')
    with open(fullpath, 'w') as outfile:
        json.dump(data, outfile, cls=CommonEncoder, indent=4)
    return fullpath.rsplit("/", 1)[1]


def account_replace(filein, num2Search, newNumber):
    # Read in the file
    with open(filein, 'r') as file:
        filedata = file.read()

    # Replace the target string
    filedata = filedata.replace(num2Search, newNumber)

    # Write the file out again
    with open(filein, 'w') as file:
        file.write(filedata)


def roleCleaner(roleString):
    if "/" in roleString or "}" in roleString:
        roleString = "_".join(roleString.split("/"))
        if "_" in roleString[0]:
            roleString = roleString[1:]
        roleString = roleString.replace("}", "")
        roleString = roleString.replace("{", "")
    if "[" in roleString:
        method = re.search(r'\[(.*?)\]', roleString).group(1)
        roleString = roleString.split("[")[0]
        if method == '*':
            method = 'all'
        roleSting = "%s_%s" % (roleString, method)
    return roleString


def loadServicesMap(fullpath, domain='RDS'):
    print(" LOADING ServiceMap: %s" % fullpath)
    if not os.path.isfile(fullpath):
        # try a directory behind
        if not fullpath.startswith("/"):
            fullpath = "../%s" % (fullpath)
            print(" LOADING 2 ServiceMap: %s" % fullpath)
    with open(fullpath, newline='') as stream:
        exp = yaml.load(stream)
    targets = exp['services'][domain]
    return targets


def loadYaml(fullpath):
    print (" LOADING: %s" % fullpath)
    if not os.path.isfile(fullpath):
        return None, None, None
    with open(fullpath, newline='') as stream:
        exp = yaml.load(stream)


def loadConfig(fullpath, env):
    print (" LOADING CONFIG: %s" % fullpath)
    if not os.path.isfile(fullpath):
        return None, None, None
    # with open(fullpath, newline='') as stream:
    with open(fullpath, 'r') as stream:
        exp = yaml.load(stream)
    env = 'target2Define' + env.capitalize()
    target = exp[env]
    global_accts = exp['accounts']
    return target, global_accts

    # END
