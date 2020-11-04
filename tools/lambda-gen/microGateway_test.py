# This code is used to create Ansible files for deploying Lambda's
# all that is needed is a target Lambda, tests, and it will do the rest.
# finds associate roles and policies
# creates Ansible modules based on those policies and roles
# defines the Lambdas and creates them with tests
# finds api-gateways or other events
# if api found defines the security needed. creates modules for deployment with templates
import re
# import ValueError
import os
import time
import random
from time import sleep
from datetime import datetime, date
import json
import shutil
import boto3
from botocore.exceptions import ClientError
import sys
from shutil import copyfile
import fileinput
import logging
import urllib

import distutils
from distutils import dir_util

from microGateway import ApiGatewayMolder


from microUtils import writeYaml, writeJSON, account_replace, loadServicesMap, loadConfig, ansibleSetup
from microUtils import describe_role, roleCleaner, loadYaml

# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
dir_path = os.path.dirname(__file__)


class ApiGatewayTester():
    origin = None
    _molder = ApiGatewayMolder("ansible")
    temp = None

    def Cooker(self, target):
        lambda_describe(target)

    def __init__(self, directory, islambda=False):
        global dir_path
        if not islambda:
            temp = "%s/%s" % (dir_path, directory)
        else:
            temp = '/tmp'
        self.temp = temp
        if not os.path.exists(temp):
            os.makedirs(temp)
        else:
            print (" directory %s already exists... remove or change name." % temp)

    # resourceNname, resourceType, aconnect, resourceRole=None, targetAPI=None
    def define(self, resourceNname, resourceType, aconnect, resourceRole, targetAPI):
        client = aconnect.__get_client__('apigateway')
        apis = self._molder.describe_gateway("*", "*", aconnect, resourceRole, targetAPI)

    #############################################
    ######   [ USAGE PLAN KEYs ]#################
    #############################################
    def test_GatewayALL(self, target, aconnect, acct, acctName, global_accts, targetAPI=None):
        print ("test_GatewayALL")
        Acct_yaml = "Ansible"
        opt = "main_%s.yaml" % (global_accts[acct]['all'])
        rootFolder = "%s/%s" % (self.temp, target)  # roles/xx
        src = "%s/%s/%s" % (rootFolder, 'defaults', opt)  # roles/xx/defaults/main_bla.yaml
        fileIN = None
        default = loadYaml(src)
        integratedAPIs, stages, final_MODELS, final_AUTHS = define('*', '*', aconnect, target, targetAPI)
        print(" look for Yaml...%s" % (src))
        apis = default[target]['api_gw']
        missing = []
        for api in apis:
            path = api['path']
            method = api['httpMethod']
            found = False
            for inter in integratedAPIs:
                if inter['path'] == path and inter['httpMethod'] == method:
                    found = True
                    break
            if not found:
                missing.append(api)
        build4Options = False
        for missed in missing:
            if missed['httpMethod'] == 'OPTIONS':
                build4Options = True
                break

        if build4Options:  # replace the skipping section
            skipping = {"methods": True, "models": True, "resources": True,
                        "options": False, "stage": False
                        }
            default[target]['skipping'] = skipping
            writeYaml(default, src, targetString)

    def test_GwResource(self, target, aconnect, acct, acctName, global_accts, targetAPI=None):
        print ("describe_GwResource for target deployments")
        # describe_gateway(self, resourceNname, resourceType, aconnect , resourceRole=None,targetAPI=None):
        # isFullUpdate = False
        client = aconnect.__get_client__('apigateway')
        apis = self.getAll_rest_apis(client)
