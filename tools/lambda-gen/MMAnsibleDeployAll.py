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
from shutil import copyfile

#from context import FormatContext
#import pyaml
# pip install pyyaml
import yaml
import decimal
from microUtils import writeYaml, writeJSON, account_replace, loadServicesMap, loadConfig, ansibleSetup
import subprocess
from subprocess import check_output
from subprocess import Popen, PIPE


# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
dir_path = os.path.dirname(__file__)
# directory='/Users/bgarner/CR/Ansible_Deployer/ansible'
directory = os.path.join(dir_path, '../../ansible')


def ansibleResetDefinition(role, target):
    rolePath = "%s/roles/%s/defaults" % (directory, role)
    main = "%s/main.yaml" % rolePath
    os.remove(main)
    copyfile("%s/main_%s.yaml" % (rolePath, target), main)
    return directory


def ansibleInvoke(account, config, role):
    roleFile = '%s.yaml' % role
    target = config['all']
    newPath = ansibleResetDefinition(role, target)
    prevPath = dir_path
    os.chdir(newPath)
    # print("test ansible path")
    # dirpath = os.getcwd()
    # print(dirpath)
    # print("test move back to ORIGINAL path")
    # os.chdir(prevPath)
    # dirpath = os.getcwd()
    # print(dirpath)
    # return

    print(roleFile)
    print(" ----- STARTING --------[%s][%s]" % (account, target))
    # quotedRole = '\"%s\"' % (roleFile)
    quotedRole = '"%s"' % (roleFile)
    # quotedRole = "'%s'" % (roleFile)
    # quotedRole = r"\'%s\'" % (roleFile)
    # quotedRole = u'\"%s\"' % (roleFile)
    args = ['ansible-playbook', '-i', 'windows-servers', quotedRole, '-vvvv']
    msg = ""
    commandIn = " ".join(args)
    try:
        print(commandIn)
        rawOut = check_output(commandIn, stderr=PIPE, shell=True).decode()
        # rawOut = check_output(args, stderr=PIPE).decode()
        # rawOut = check_output(args, stderr=PIPE, shell=True).decode()
        if isinstance(rawOut, str):
            output = rawOut
        else:
            output = rawOut.decode("utf-8")
        msg = output
    except Exception as e:
        msg = "[E] error occured target:%s  file:%s error:%s" % (target, roleFile, e)
        print(msg)
    # process = Popen(args, stdout=PIPE, stderr=PIPE)#, timeout=timeout)
    # stdout, stderr = process.communicate()  #will wait without deadlocking
    #print (stdout)
   # print (stderr)
    print(" ----- COMPLETED --------[%s][%s]" % (account, target))

    os.chdir(prevPath)
    return account, target, msg


def deployStart(accounts, targets, role, HardStop=False):
    outputs = {}
    for target in targets:
        for k, v in accounts.items():
            if target in v['all']:
                account, target, result = ansibleInvoke(k, v, role)
                outputs.update({account: {"name": target, "value": result}})
                if HardStop:
                    if '[E]' in result:
                        return outputs
                break
    return outputs
# cp -R /usr/local/src/venvs/vdocx3/lib/python3.6/site-packages/slacker /path/to/Lambda
# ansible-playbook -i windows-servers xx_tablename.yaml -vvvv

    # python MMAnsibleDeployAll.py "xx-stage,xx-test" xx_tablename ENVR.yaml
    #
    # python MMAnsibleDeployAll.py "stage,prod" API_Name ENVR.yaml


# OR call it manually in /ansible folder
    #  ansible-playbook -i windows-servers xx-LambdaName -vvvv


if __name__ == "__main__":
    found = None
    length = 0
    target_environments = str(sys.argv[1]).strip().split(",")
    role = str(sys.argv[2]).strip()
    config = str(sys.argv[3]).strip()
    start_time = time.time()

    fullpath = "%s/%s" % (dir_path, config)
    origin, global_accts = loadConfig(fullpath, "dev")
    results = deployStart(global_accts, target_environments, role)
    for k, v in results.items():
        msg = "%s Account: %s, %s" % (v['name'], k, v['value'])
        print(msg)

    # print(global_accts)

    #print (target_environments)
    #//logger.info("Finished")

    print("--- %s seconds ---" % (time.time() - start_time))
