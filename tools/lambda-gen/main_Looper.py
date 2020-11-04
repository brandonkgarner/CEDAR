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
from microUtils import loadConfig, roleCleaner
from MMAnsibleDeployAll import deployStart
from main_Deployer import TemporalDeployer
import awsconnect
from awsconnect import awsConnect


# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
dir_path = os.path.dirname(__file__)
# directory='/Users/bgarner/CR/Ansible_Deployer/ansible'
directory = os.path.join(dir_path, '../../ansible')

# EXECUTE AGAINST DEFINITIONS
#
#
# PRODUCE RESULTS PASS/FAIL
# python microMolder.py -L xx-LambdaName true ENVR.yaml '/path/to/Ansible_Deployer/ansible/roles/xx-LambdaName' API_Name true
# python Main_DEPLOYER.py -DY dev "test,stage" xx_tablename ENVR.yaml '/path/to/Ansible_Deployer/ansible/roles/xx-LambdaName' API_Name true
#. OR
# python Main_DEPLOYER.py "xx-stage,xx-test" xx_tablename ENVR.yaml
# python Main_Deployer.py "xx-test" xx_tablename ENVR.yaml
if __name__ == "__main__":
    SkipDefinition = False
    start_time = time.time()
    config = "ENVR.yaml"
    fullpath = "%s/%s" % (dir_path, config)
    origin, global_accts = loadConfig(fullpath)
    triggers = origin['triggers']
    if triggers is None:
        raise ValueError("[E] config file [ %s ] did not load correctly.. PLEASE check / fix and try again" % (fullpath))

    td = TemporalDeployer()

    targetAPI = fullUpdate = target_environments = None

    # environments="party3d"
    # environments="test"
    # environments="final"
    environments = "test,stage,prod,final"

    ##############################################################
    ######### don't forget to update ENVR.yaml#############
    ##############################################################
    #  target2Define -->must update the EID, name and

    target_environments = environments.split(",")
    type_in = "-DY"  # -DY  #-G -L
    targetAPI = "API_Name"
    fullUpdate = True
    # root="/Users/bgarner/CR/Ansible_Deployer/ansible/roles"
    root = os.path.join(dir_path, "../../ansible/roles")
    for role in dynamo:
        ready = None
        # role = roleCleaner(role)
        roleString = roleCleaner(role)
        sendto = "%s/%s" % (root, roleString)
        if not SkipDefinition:
            acctID, target, acctTitle, ready = td.Define(type_in, role, origin, global_accts, sendto, config, triggers, targetAPI, fullUpdate)
            print("-[DEFINED]-- %s seconds ---" % (time.time() - start_time))

        if ready or SkipDefinition:
            print("###########################################################")
            print("######### Ansible DEPLOYMENT START [%s] ##################%s" % (type_in, roleString))
            print("###########################################################")
            results = deployStart(global_accts, target_environments, roleString)
            for k, v in results.items():
                msg = "%s Account: %s, %s" % (v['name'], k, v['value'])
                print(msg)
            print("-[DEPLOYED]-- %s seconds ---" % (time.time() - start_time))

    # print(global_accts)

    #print (target_environments)
    #//logger.info("Finished")

    print("--[FIN]- %s seconds ---" % (time.time() - start_time))
