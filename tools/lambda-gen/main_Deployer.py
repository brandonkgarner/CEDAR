import os
import sys
import re
from time import sleep
import time
import random

from microMolder import LambdaMolder
from microFront import CloudFrontMolder
from microGateway import ApiGatewayMolder
from microDynamo import DynamoMolder
from microUtils import loadConfig, roleCleaner, serviceID
from MMAnsibleDeployAll import deployStart
# TESTERS...
from microGateway_test import ApiGatewayTester

import awsconnect
from awsconnect import awsConnect


# sudo ansible-playbook -i windows-servers API_Name.yaml -vvvv
dir_path = os.path.dirname(__file__)
real_dir_path = os.path.dirname(os.path.realpath(__file__))
# directory='/path/to/Ansible_Deployer/ansible'

# python Main_DEPLOYER.py -DY dev "test,stage,prod,tpp"  "xx_tablename" ENVR.yaml API_Name true


class TemporalDeployer():

    def __init__(self, directory=None):
        pass

# CREATE DEFINITIONS

    def Define(self, type_in, svc_in, origin, global_accts, sendto, config, triggers=None, targetAPI=None, fullUpdate=None):
        accID = origin['account']
        region = origin['region']
        accountRole = global_accts[accID]['role']
        print(" ## USING ## %s--> %s, role %s, account originDefinition %s, config %s, copyAnsible to %s" %
              (type_in, svc_in, accountRole, accID, config, sendto))
        print(" !!! !! to assume <cross_acct_role> ROLE make sure you set 'assume_role' in 'ENVR.yaml' to True or False as needed")
        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
        print(" ________________-")
        print("         %s" % (accID))
        print(" ________________-")
        if 'eID' in origin:
            eID = origin['eID']
        if 'services_map' in origin:
            mapfile = origin['services_map']
            eID = serviceID(origin['account'], mapfile, origin['all'])

        aconnect = awsConnect(
            accID, eID, origin['role_definer'], sts_client, region)
        aconnect.connect()
        results = None
        if type_in == "-CF":
            cm = CloudFrontMolder("ansible")
            acctID, target, acctTitle, ready = cm.cfront_describe(
                svc_in, aconnect, origin, global_accts, sendto)
            print("CF here")
        elif type_in == "-L":
            lm = LambdaMolder("ansible")
            acctID, target, acctTitle, ready = lm.lambda_describe(
                svc_in, aconnect, origin, global_accts, triggers, sendto, targetAPI, fullUpdate)
        elif type_in == "-G":
            gm = ApiGatewayMolder("ansible")
            if targetAPI == svc_in:
                acctID, target, acctTitle, ready = gm.describe_GatewayALL(
                    svc_in, aconnect, origin, global_accts, triggers, sendto, targetAPI, fullUpdate, True)
            else:
                acctID, target, acctTitle, ready = gm.describe_GwResource(
                    svc_in, aconnect, origin, global_accts, triggers, sendto, targetAPI, fullUpdate, True)
        elif type_in == "-DY":
            dy = DynamoMolder("ansible")
            acctID, target, acctTitle, ready = dy.define(
                svc_in, aconnect, origin, global_accts, sendto)
        return acctID, target, acctTitle, ready


# CHECK GATEWAY FOR OPTIONS. LOOK TO SEE IF OPTIONS ARE THERE!!!

    def TEST(self, type_in, svc_in, acct, acctName, global_accts, config, targetAPI):
        accID = acct
        region = 'us-east-1'
        accountRole = global_accts[accID]['role']
        print(" ## OPTIONS TEST ## %s--> %s, role %s, account originDefinition %s, config %s, copyAnsible to %s" %
              (type_in, svc_in, accountRole, accID, config, sendto))
        print(" !!! [TEST] !! to assume <cross_acct_role> ROLE make sure you set 'assume_role' in 'ENVR.yaml' to True or False as needed")
        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
        eID = 10000010001
        if 'eID' in global_accts[accID]:
            eID = global_accts[accID]['eID']
        aconnect = awsConnect(accID, eID, accountRole, sts_client, region)
        aconnect.connect()
        results = None
        if type_in == "-CF":
            cm = CloudFrontMolder("ansible")
            print("CF TEST here")
        elif type_in == "-L":
            lm = LambdaMolder("ansible")
            print("LAMBDA TEST here")
        elif type_in == "-G":
            gm = ApiGatewayTester("ansible")
            print("GATEWAY TEST here")
            if targetAPI == svc_in:
                errors = gm.test_GatewayALL(
                    svc_in, aconnect, acct, acctName, global_accts, targetAPI)
            else:
                errors = gm.test_GwResource(
                    svc_in, aconnect, acct, acctName, global_accts, targetAPI)
        elif type_in == "-DY":
            dy = DynamoMolder("ansible")
            print("DYNAMO TEST here")
        return errors


# EXECUTE AGAINST DEFINITIONS
#
#
# PRODUCE RESULTS PASS/FAIL
# python microMolder.py -L xx-LambdaName true ENVR.yaml API_Name true
# python Main_DEPLOYER.py -DY dev "test,stage" xx_tablename ENVR.yaml API_Name true
# python Main_DEPLOYER.py -G dev "stage" API_Name ENVR.yaml API_Name true
# . OR
# python Main_DEPLOYER.py "xx-stage,xx-test" xx_tablename ENVR.yaml
# python Main_Deployer.py "xx-test" xx_tablename ENVR.yaml
#
#
#
if __name__ == "__main__":
    # global directory
    directory = os.path.join(dir_path, '../../ansible')
    found = None
    length = 0
    tot = len(sys.argv) - 1
    SkipDefinition = False
    type_in = str(sys.argv[1]).strip()
    if 'help' in type_in:
        print(" ************************************************************")
        print("      Try using the following PSUEDO after *CONFIG.yaml is correct :")
        print('           python Main_DEPLOYER.py -L dev "test,stage" * ENVR.yaml API_Name true')
        print(
            "         -[NOTE]-->  the above will describe 'dev' and then deploy ALL * to 'test,stage' ")
        print(
            "         -[NOTE]-->  the above will describe 'dev' and then deploy to 'test,stage' ")
        print(
            "         -[NOTE]-->  the above can also deploy API only using -G , CloudFront using -CF, DynamoDB using -DY  ")
        print(
            '           python Main_DEPLOYER.py -G dev "test,stage" activities[*] ENVR.yaml API_Name true')
        print(
            "         -[NOTE]-->  the above will describe activities api with all methods * ")
        print(
            '           python Main_DEPLOYER.py -G dev "test,stage" *[*] ENVR.yaml API_Name true')
        print('           python Main_DEPLOYER.py -G dev "test,stage" API_Name ENVR.yaml API_Name true')
        print(
            "         -[NOTE]-->  the above will deploy all API under API_Name... both rolename(API_Name) and targetAPI MUST be SAME  ")
        print("         OR to deploy without Defining ")
        print("         -[NOTE]-->  the above will deploy to stage,test ")
        print(" ************************************************************")
        exit()

    targetAPI = fullUpdate = target_environments = None
    if tot < 6:
        missing = 6 - tot
        totTypeIn = len(type_in)
        msg = "[E] %s arguments missing... found:%s needs 6+ arguments" % (
            missing, tot)
        if "-" in type_in and totTypeIn < 4:
            example = "... for example: \n   python Main_DEPLOYER.py -L dev 'test,stage' Quickboks_temp ENVR.yaml"
            msg = "%s %s" % (msg, example)
            raise Exception(msg)
        elif totTypeIn > 4:
            SkipDefinition = True
    if not SkipDefinition:
        source_environment = str(sys.argv[2]).strip()
        target_environments = str(sys.argv[3]).strip().split(",")
        role = str(sys.argv[4]).strip()
        config = str(sys.argv[5]).strip()  # ENVR.yaml
        if '/' in str(sys.argv[6]):
            sendto = str(sys.argv[6]).strip()  # 'some path'
        else:
            sendto = os.path.join(dir_path, '../../ansible/roles')
            sys.argv.append(sys.argv[7])
            sys.argv[7] = sys.argv[6]
        roleString = roleCleaner(role)
        if not "roles/" in sendto:
            sendto = "%s/%s" % (sendto, roleString)
        # targetAPI = str(sys.argv[7]).strip()   ### API_Name
        if len(sys.argv) > 7:
            targetAPI = str(sys.argv[7]).strip()
            print(sys.argv[7])
            if targetAPI.lower() == "none" or targetAPI.lower() == "null" or targetAPI == "*":
                targetAPI = None
        # fullUpdate = str(sys.argv[8]).strip()   ### true
        if tot > 8:
            fullUpdate = str(sys.argv[8]).strip().lower()  # true
            if fullUpdate == "none" or fullUpdate == "null" or fullUpdate == "false":
                fullUpdate = False
            else:
                fullUpdate = True
    else:
        target_environments = type_in.split(",")
        role = str(sys.argv[2]).strip()
        config = str(sys.argv[3]).strip()

    start_time = time.time()

    fullpath = "%s/%s" % (real_dir_path, config)
    origin, global_accts = loadConfig(fullpath, source_environment)
    # if 'eID' in origin:
    #     eID = origin['eID']
    # if 'services_map' in origin:
    #     mapfile = origin['services_map']
    #     eID = serviceID(origin['account'], mapfile, origin['all'])
    triggers = origin['triggers']
    if triggers is None:
        raise ValueError(
            "[E] config file [ %s ] did not load correctly.. PLEASE check / fix and try again" % (fullpath))
    td = TemporalDeployer()
    ready = None

    if not SkipDefinition:
        acctID, target, acctTitle, ready = td.Define(
            type_in, role, origin, global_accts, sendto, config, triggers, targetAPI, fullUpdate)
        print("-[DEFINED]-- %s seconds ---" % (time.time() - start_time))
        # BELOW to skip deployment
        # exit()

    if ready or SkipDefinition:
        deploy_time = time.time()
        print("########################################################")
        print("########### Ansible DEPLOYMENT START  ##################")
        print("########################################################")
        role = role
        results = deployStart(global_accts, target_environments, roleString)
        for k, v in results.items():
            msg = "%s Account: %s, %s" % (v['name'], k, v['value'])
            print(msg)
            if "-G" in type_in:
                acct = v['value']
                acctName = v['name']
                print(" GATEWAY releasing ---> checking OPTIONS")
                # acctID, target, acctTitle, ready = td.TEST(type_in,role,acct,acctName,global_accts,config,targetAPI)

        print("-[DEPLOYED]-- %s seconds ---" % (time.time() - deploy_time))

    # print(global_accts)

    #print (target_environments)
    # //logger.info("Finished")

    print("--[FIN]- %s seconds ---" % (time.time() - start_time))
