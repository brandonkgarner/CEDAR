# This code is used to create Ansible files for deploying Lambda's
# all that is needed is a target Lambda, tests, and it will do the rest.
# finds associate roles and policies
# creates Ansible modules based on those policies and roles
# defines the Lambdas and creates them with tests
# finds api-gateways or other events
# if api found defines the security needed. creates modules for deployment with templates
import re
from time import sleep
import os,time, random
import shutil
from datetime import datetime, date
import boto3
from botocore.exceptions import ClientError
import  json
import sys
from shutil import copyfile
import fileinput
import logging
import urllib

import distutils
from distutils import dir_util

import awsconnect

from awsconnect import awsConnect


from microUtils import writeYaml, writeJSON, account_replace, loadServicesMap, loadConfig, ansibleSetup

#sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
dir_path = os.path.dirname(__file__)


class CloudFrontMolder():
  origin = None

  temp=None
  def __init__(self, directory):
    global dir_path
    temp="%s/%s"%(dir_path,directory)
    self.temp=temp
    if not os.path.exists(temp):
        os.makedirs(temp)
    else:
        print (" directory %s already exists... remove or change name."%temp)



  def Cooker(self,target):
    lambda_describe(target)



  def behavior_describe(self, target, aconnect ):
    #client = boto3.client('lambda')
    client = aconnect.__get_client__('cloudfront')
    originID = None
    listCF = client.list_distributions()
    if not 'DistributionList' in listCF:
        raise ValueError("[E] DistributionList Not found (%s) PLEASE check / fix and try again"%(target))
    if not 'Items' in listCF['DistributionList']:
        raise ValueError("[E] DistributionList Not found (%s) PLEASE check / fix and try again"%(target))
    lcf =listCF['DistributionList']['Items']
    for cf in lcf:
        cf['Status']
        if target.lower() in cf['DefaultCacheBehavior']['TargetOriginId'].lower():
            originID=cf['Id']
            break

    cfd = client.get_distribution( Id=originID )['Distribution']

    CacheBehaviors = cfd['DistributionConfig']['CacheBehaviors']
    # Origins = cfd['DistributionConfig']['Origins']
    # DefaultBehavior = cfd['DistributionConfig']['DefaultCacheBehavior']
    # Alias=cfd['DistributionConfig']['Aliases']

    return type('obj', (object,), {
                'id':cfd['Id'],
                'target':target,
                's3': CacheBehaviors['Items'][0]['TargetOriginId'][3:],
                'status':cfd['Status'],
                'arn':cfd['ARN'],
                'activeSigners':cfd['ActiveTrustedSigners'],
                'distribution_config':cfd['DistributionConfig']
                }
            )


#  python microMolder.py -CF cr-portal-dev true ENVR.yaml '/Users/astro_sk/Documents/TFS/Ansible_Deployer/ansible/roles/CR-Cfront'

  def cfront_describe(self, target, aconnect, accountOrigin,  accounts=[],  sendto=None):
    self.origin=accountOrigin
    acctID = accountOrigin['account']
    assumeRole = accountOrigin['assume_role']
    cfrontM = self.behavior_describe(target, aconnect)
    acctTitle = None

    taskMain,rootFolder,targetLabel=ansibleSetup(self.temp,target, True)
    #############################################
    #############################################
    ######## write YAML to file in tasks  #######
    #############################################
    #############################################
    option = "main"
    mainIn = "%s/%s/%s"%(rootFolder,'tasks',option)
    writeYaml(taskMain, mainIn )
    skipping=error_path=None
    if 'error_path' in accountOrigin:
        error_path = accountOrigin['error_path']
    if 'skipping' in accountOrigin:
        skipping = accountOrigin['skipping']
    # error_path: /Users/astro_sk/Documents/TFS/Ansible_Deployer
    if not skipping:
        skipping = {
            "methods": False,
            "options": False,
            "models": False,
            "stage": False,
            "resources": False
        }
    #############################################
    ###########   END WRITE  ####################
    #############################################
    #############################################


    for akey,account in accounts.items():
        if acctID ==akey:
            acctTitle=account['title']
        accDetail={
            "account_id": akey,
            "error_path": error_path,
            "skipping":skipping,
            "env": account['title'],
            "role_duration": 3600,
            "region": "us-east-1",
            "eid": account['eID']
        }
        defaultVar = {targetLabel:accDetail}
        cfront={
            'id':cfrontM.id,
            'target':cfrontM.target,
            's3': cfrontM.s3,
            'status':cfrontM.status,
            'arn':cfrontM.arn,
            'activeSigners': cfrontM.activeSigners,
            'distribution_config': cfrontM.distribution_config
        }
        defaultVar[targetLabel].update({"cloudfront":cfront})


        option = "main_%s"%account['all']
        mainIn = "%s/%s/%s"%(rootFolder,'defaults',option)
        writeYaml(defaultVar, mainIn )
        account_replace("%s.yaml"%mainIn, str(acctID), str(akey))

    if not sendto is None:
        print (" .... creating a main.yaml for ansible using dev")
        opt = "main_%s.yaml"%accountOrigin['all']
        src = "%s/%s/%s"%(rootFolder,'defaults',opt)
        opt2 = "main.yaml"
        dst = "%s/%s/%s"%(rootFolder,'defaults',opt2)
        copyfile(src, dst)
        print (" -------==------===---- COPY START....")
        print (" sending to %s. from %s"%(sendto,rootFolder))
        distutils.dir_util.copy_tree(rootFolder, sendto)
    return acctID, target, acctTitle, True






  def cfront_create(self, target, aconnect, accountOrigin,  accountTarget):
    client = aconnect.__get_client__('cloudfront')
    listCF = client.list_distributions()['DistributionList']
    lcf =listCF['DistributionList']['Items']
    originID=None
    for cf in lcf:
        cf['Status']
        if target.lower() in cf['DefaultCacheBehavior']['TargetOriginId'].lower():
            originID=cf['Id']
            break
    if originID is None:
        response = client.create_distribution(DistributionConfig={})
    else:
        response = client.update_distribution(Id=originID, DistributionConfig={})




if __name__ == "__main__":
    found=None
    length=0
    try:
        sys.argv[1]
        found=sys.argv
        length=len(found)
    except:
        found = "help"
        #ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
        #ansible-playbook -i windows-servers CR-WriteCheck.yml -vvvv
## python microFront.py cr-portal-dev ENVR.yaml '/Users/astro_sk/Documents/TFS/Ansible_Deployer/ansible/roles/CR-Adhoc' '/Users/astro_sk/Documents/TFS/Ansible_Deployer/ansible/roles/CR-Adhoc'
    if "help" in found and length<3:
        print(" ************************************************************")
        print("      Try using the following PSUEDO after *CONFIG.yaml is correct :")
        print("           python microFront.py distribution useRoleDeployer configYaml fromYaml")
        print("         -[NOTE]--> 'useRoleDeployer' and 'sendto' and 'targetAPI' can be passed as null  for all ")
        print("      REAL example when using STS (cross deploy role):")
        print("           python microFront.py cr-portal-dev CR-Admin-Users ENVR.yaml '/Users/astro_sk/Documents/TFS/Ansible_Deployer/ansible/roles/CR-Admin-Users.yaml'")
        print(" ************************************************************")
        exit()
    else:
        print ("  ..... INIT..... 0001 ")
        target = str(sys.argv[1]).strip()
        useRoleDeployer = str(sys.argv[2]).strip()
        if useRoleDeployer.lower() == "none" or useRoleDeployer.lower() == "null" or useRoleDeployer.lower() == "false":
            useRoleDeployer=None
        config = str(sys.argv[3]).strip()
        #config='ENVR.yaml'
        targetConfig = str(sys.argv[4]).strip()
        if targetConfig.lower() == "none" or targetConfig.lower() == "null":
            targetConfig=None

        #sendto ="/Users/astro_sk/Documents/TFS/Ansible_Deployer/ansible/roles/CR-Admin-Users"

        logging.basicConfig(format='%(asctime)-15s %(message)s')
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        logger.info("Started")
        print ("  ..... CloudFRont CREATE..... 0002")

        fullpath="%s/%s"%(dir_path,config)
        origin, global_accts=loadConfig(fullpath)
        triggers = origin['triggers']
        if triggers is None:
            raise ValueError("[E] [CF] config file [ %s ] did not load correctly.. PLEASE check / fix and try again"%(fullpath))
        accID=origin['account']
        region =  origin['region']
        accountRole=global_accts[accID]['role']
        print (" ## USING ## %s--> %s, role %s, account originDefinition %s, config %s, copyAnsible to %s"%(type_in,svc_in, accountRole, accID,  config, targetConfig))
        print (" !!! !! to assume <cross_acct_role> ROLE make sure you set 'assume_role' in 'ENVR.yaml' to True or False as needed")
        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
        aconnect = awsConnect( accID, origin['eID'], origin['role_definer'], sts_client, region)
        aconnect.connect()


        cm = CloudFrontMolder("ansible")
        cm.cftont_create(self, target, aconnect, origin,  targetConfig)
        print ("CF here")

        logger.info("Finished")

#  python microMolder.py -CF cr-portal-dev true ENVR.yaml '/Users/astro_sk/Documents/TFS/Ansible_Deployer/ansible/roles/CR-Cfront'

















