#!/usr/bin/python


DOCUMENTATION = '''
---
module: kms_cd
short_description: list keys in KMS.
description:
    - This module allows the user to manage keys in KMS. Includes support for creating and deleting keys, retrieving keys . This module has a dependency on python-boto.
version_added: "1.1"
options:
  aws_access_key:
    description:
      - AWS access key id. If not set then the value of the AWS_ACCESS_KEY environment variable is used.
    required: false
    default: null
    aliases: [ 'ec2_access_key', 'access_key' ]
  aws_secret_key:
    description:
      - AWS secret key. If not set then the value of the AWS_SECRET_KEY environment variable is used.
    required: false
    default: null
    aliases: ['ec2_secret_key', 'secret_key']
  name:
    description:
      - name of KMS key.
    required: true
    default: null
    aliases: []
  state:
    description:
      - Create or remove keys
    required: false
    default: present
    choices: [ 'present', 'absent' ]
  action:
    description:
      - encrypt or decrypt, decrypt can only occur if key already exists and was used previously.
    required: false
    default: null
    choices: [ 'encrypt', 'decrypt' ]
  target_data:
    description:
      - data that needs to be encrypted or decrypted. field requires action
    required: false
    default: null
'''

EXAMPLES = '''
- name: list KMS keys
  kms_cd:
    github_auth_key: "..."
    name: "Hello-World"
    description: "This is your first repository"
    private: yes
    has_issues: no
    has_wiki: no
    has_downloads: no
  register: result
- name: Delete that repo 
  github_repo:
    github_auth_key: "..."
    name: "Hello-World"
    state: absent
  register: result
'''

import base64
import copy
import math
import multiprocessing as mp

from pytz import timezone

try:
    import boto3
    from botocore.exceptions import ClientError, MissingParametersError, ParamValidationError
    HAS_BOTO3 = True

    from botocore.client import Config
    import boto3.dynamodb
    from  boto3.dynamodb.types import STRING, NUMBER, BINARY
    from boto3.dynamodb.table import TableResource as Table
    from boto3.dynamodb.conditions import Key, Attr
except ImportError:
    import boto
    HAS_BOTO3 = False

from jenkinsapi.jenkins import Jenkins
try:
    import jenkins
    python_jenkins_installed = True
except ImportError:
    python_jenkins_installed = False

try:
    from lxml import etree as ET
    python_lxml_installed = True
except ImportError:
    python_lxml_installed = False

ARG_SPEC=None
module=None
jenkinsAgent=None
class JenkinsAgent:
    def __init__(self, module,client,resource):
        global jenkinsAgent
        jenkinsAgent = self
        self.module = module
        self.client=client
        self.resource=resource
        self.mins_toStop = module.params.get('mins_toStop')
        self.name = module.params.get('name')
        self.type = module.params.get('type')
        self.password = module.params.get('password')
        self.token = module.params.get('token')
        self.user = module.params.get('user')
        self.jenkins_url = module.params.get('url')
        self.roleUsed = module.params.get('roleUsed')
        self.profile = module.params.get('profile_ec2')
        self.server = self.get_jenkins_connection()
        self.facts = module.params.get('facts')
        self.spot_enabled = module.params.get('spot_enabled')
        self.api = self.get_jenkins_api()

        self.result = {
            'changed': False,
            'url': self.jenkins_url,
            'name': self.name,
            'user': self.user,
            'added': [],
            'removed':[],#{'Name':'cd-ansible-windows-builder-RC23', 'JENKINS':'windows'},
            'started':[],
            'stopped':[],
            'warn':[],
        }

        # This kind of jobs do not have a property that makes them enabled/disabled
        self.job_classes_exceptions = ["jenkins.branch.OrganizationFolder"]

        self.EXCL_STATE = "excluded state"

    def get_node_label(self, node_str):
        #time.sleep(1)  #make sure defaults URL in JENKINS are BLANK
        #self.module.fail_json(msg=' get_node_label %s' % (node_str) )
        configXML_raw = self.server.get_node_config(node_str)
        configXML = "\n".join(configXML_raw.split("\n")[1:])
        _element_tree = ET.fromstring(configXML)
        node_labels = _element_tree.find('label').text
        return node_labels

    def get_job_label(self, job_str):
        #time.sleep(1)  #make sure defaults URL in JENKINS are BLANK
        #self.module.fail_json(msg=' get_job_label %s' % (job_str) )
        instJob = self.api.get_job(job_str)
        configXML_raw = instJob.get_config()
        #configXML_raw = self.server.get_job_config(job_str)
        #configXML = "\n".join(configXML_raw.split("\n")[1:])
        configXML = "\n".join(configXML_raw.split("\n")[1:])
        _element_tree = ET.fromstring(configXML)
        node_labels = _element_tree.find('assignedNode').text
        return node_labels

    def get_jenkins_api(self):
        try:
            if (self.user and self.password):
                return Jenkins(self.jenkins_url, self.user, self.password)
            elif (self.user and self.token):
                return Jenkins(self.jenkins_url, self.user, self.token)
            elif (self.user and not (self.password or self.token)):
                return Jenkins(self.jenkins_url, self.user)
            else:
                return Jenkins(self.jenkins_url)
        except Exception:
            e = get_exception()
            self.module.fail_json(msg='Unable to connect to Jenkins API, %s' % str(e))

    def get_jenkins_connection(self):
        try:
            if (self.user and self.password):
                return jenkins.Jenkins(self.jenkins_url, self.user, self.password)
            elif (self.user and self.token):
                return jenkins.Jenkins(self.jenkins_url, self.user, self.token)
            elif (self.user and not (self.password or self.token)):
                return jenkins.Jenkins(self.jenkins_url, self.user)
            else:
                return jenkins.Jenkins(self.jenkins_url)
        except Exception:
            e = get_exception()
            self.module.fail_json(msg='Unable to connect to Jenkins server, %s' % str(e))

    def job_class_excluded(self, response):
        return response['_class'] in self.job_classes_exceptions

    def get_job_status(self):
        try:
            response = self.server.get_job_info(self.name)
            if self.job_class_excluded(response):
                return self.EXCL_STATE
            else:
                return response['color'].encode('utf-8')

        except Exception:
            e = get_exception()
            self.module.fail_json(msg='Unable to fetch job information, %s' % str(e))

    def job_exists(self):
        try:
            return bool(self.server.job_exists(self.name))
        except Exception:
            e = get_exception()
            self.module.fail_json(msg='Unable to validate if job exists, %s for %s' % (str(e), self.jenkins_url))

    def get_config(self):
        return job_config_to_string(self.config)

    def get_current_config(self):
        return job_config_to_string(self.server.get_job_config(self.name).encode('utf-8'))

    def has_config_changed(self):
        # config is optional, if not provided we keep the current config as is
        if self.config is None:
            return False

        config_file = self.get_config()
        machine_file = self.get_current_config()

        self.result['diff']['after'] = config_file
        self.result['diff']['before'] = machine_file

        if machine_file != config_file:
            return True
        return False

    def present_job(self):
        if self.config is None and self.enabled is None:
            self.module.fail_json(msg='one of the following params is required on state=present: config,enabled')

        if not self.job_exists():
            self.create_job()
        else:
            self.update_job()

    def has_state_changed(self, status):
        # Keep in current state if enabled arg_spec is not given
        if self.enabled is None:
            return False

        if ( (self.enabled == False and status != "disabled") or (self.enabled == True and status == "disabled") ):
            return True
        return False

    def switch_state(self):
        if self.enabled == False:
            self.server.disable_job(self.name)
        else:
            self.server.enable_job(self.name)

    def update_job(self):
        try:
            status = self.get_job_status()

            # Handle job config
            if self.has_config_changed():
                self.result['changed'] = True
                if not self.module.check_mode:
                    self.server.reconfig_job(self.name, self.get_config())

            # Handle job disable/enable
            elif (status != self.EXCL_STATE and self.has_state_changed(status)):
                self.result['changed'] = True
                if not self.module.check_mode:
                    self.switch_state()

        except Exception:
            e = get_exception()
            self.module.fail_json(msg='Unable to reconfigure job, %s for %s' % (str(e), self.jenkins_url))


    def agentTypes(self,defined_agents):
        return [instance['type'] for instance in defined_agents]
    def agentCleanToEC2(self, ec2_instances):
        jnodes = self.facts['nodes']
        resource = self.resource
        for node in jnodes:
            nname=node['name']
            if '_i-' not in nname:
                continue
            ename=nname.split('_i-')
            label=ename[0]
            eid='i-%s'%ename[1]
            try:
                instance = resource.Instance(eid)
                if instance.state['Name'] == 'terminated':
                    self.nodeDelete(eid, label)
                    time.sleep(1)
                    self.result['warn'].append(' [W] node %s found without matching EC2 instance id:%s' % (nname, eid))
            except Exception as error:
                #instance not found so delete node from jenkins
                self.nodeDelete(eid,label)
                time.sleep(1)
                self.result['warn'].append(' [W] node %s found without matching EC2 instance id:%s'%( nname, eid ) )


    def totalRawSlavesNeeded(self):
        jobs = self.facts['jobs']
        max_agents=len(jobs)
        building = self.facts['building']
        queues = self.facts['queues']


        neededList={}
        for build in building:
            nodeName=build['node']
            label= self.get_node_label(nodeName)
            if label in neededList:  #label found in building...
                neededList[label]=0
                neededList['running'].append(nodeName)
            else:
                neededList.update({label:0,'running':[nodeName]} )
        ### amsdevelopment
        for q in queues:
            #job_name=q['url'].split('/job/')[:-1]
            #module.fail_json(msg="  queues Error - {0}".format(q))
            job_name=q['task']['name']
            label=self.get_job_label(job_name)
            if label in neededList:
                neededList[label]=neededList[label]+1
            else:
                neededList.update({label:0} )
        return neededList
    #consolicate instances found on spot requests and map against running instances on demand
    def slaveExisting(self, filters, ec2_state):
        resource = self.resource
        filters =copy.copy(filters)
        client = self.client
        existing_ALL=[]
        requests = client.describe_spot_instance_requests(Filters=filters)['SpotInstanceRequests']
        for rq in requests:
            existing_ALL
            instance = resource.Instance(rq['InstanceId'])
            inst = copy.copy(instance.meta.data)
            #add tags from filters as a precaution
            if 'running' in inst['State'] or 'pending' in inst['State']:
                existing_ALL.append({'InstanceId':inst['InstanceId'], 'Tags':filters, 'State':inst['State'], 'Spot': True})
        efilters =copy.copy(filters)
        efilters.append(ec2_state)
        existing = list(resource.instances.filter(Filters=filters))  # instance  id/tags/state/platform
        for ex in existing:   #filter already uses state values to pick up NON terminated instances
            inst = copy.copy(ex.meta.data)
            found =False
            for e_inst in existing_ALL:
                if e_inst['InstanceId'] in inst['InstanceId']:
                    found=True
                    break
            if not found:  ## add these boxes 1st since ondemand
                existing_ALL.insert(0,
                    {'InstanceId': inst['InstanceId'], 'Tags': filters, 'State': inst['State'], 'Spot': False})
        return existing_ALL

    def slaveDistribute(self):
        jenkinsKey = self.module.params.get('tag_key')
        now_utc = datetime.datetime.now(timezone('UTC'))
        defined_agents = self.module.params.get('agents')    ## agent definitions
        waiting_reserve = self.module.params.get('waiting_reserve')    ## reservation #'s needed to meet


        resource=self.resource
        agent_Types= self.agentTypes(defined_agents)

        #find possible impaired instances and removed before starting our count
        pName = self.profile


        for agent in defined_agents:    # loop to get possible impaired instance
            ec2_SubnetId = agent['vpc_subnet_id']
            subnet = resource.Subnet(ec2_SubnetId)
            zone = subnet.availability_zone
            filters = [{'Name': 'system-status.status', 'Values': ['impaired']},
                       {'Name': 'availability-zone', 'Values': [zone]},
                       {'Name': 'instance-state-name', 'Values': ['running']}]
            etager = self.client.describe_instance_status(Filters=filters)['InstanceStatuses']
            for inst in etager:
                meID = inst['InstanceId']
                rInst = self.resource.Instance(meID)
                prfile = rInst.iam_instance_profile
                if pName in prfile['Arn']:  #profile name found in instance profile definition so delete
                   ## let these dye  they are B R O K E N  IMPAIRD
                    rInst.terminate()
                    self.nodeDelete(meID,agent['type'])
                    #rInst.wait_until_terminated()

        slavesNeeded = self.totalRawSlavesNeeded()  #label:total_ec2 NEEDED
        ec2_state={'Name':'instance-state-name','Values':['running', 'stopped', 'pending', 'stopping', 'rebooting']}

        filters=[ {'Name':'tag:%s'%self.module.params.get('tag'), 'Values': agent_Types} ]
        ##  'stopped'  'terminated'
        existing = self.slaveExisting(filters, ec2_state) #instance  id/tags/state/platform
        self.agentCleanToEC2(existing)

        self.agentStandby(defined_agents, agent_Types, waiting_reserve, existing, slavesNeeded)

        filters.append(ec2_state)
        finalServers = list(resource.instances.filter(Filters=filters))

        self.result['changed']=True

        return self.result


    # waiting_reserves need to ALWAYS be "on Demand" since SPOT takes too long to load
    def agentStandby(self, defined_agents, agent_Types, waiting_reserves, existing, neededSLAVES):
        #delete all other servers that arent' part of the waiting_reserves
        jenkinsKey = self.module.params.get('tag_key')
        run_time_mins = self.mins_toStop   #at least this NUMBER of mins before stop or terminating
        now_utc = datetime.datetime.now(timezone('UTC'))
        spot_enabled = self.spot_enabled
        totalFound={}
        for inst in existing:
            #inst = copy.copy(instance.meta.data)
            tags = inst['Tags']
            eID=inst['InstanceId']
            tagMain = dict([tag['Key'], tag['Value']] for tag in tags)
            for atype in agent_Types:  # FIND EC2 boxes being USED and REMOVE from LIST
                name = "%s_%s" % (atype, eID)
                if 'running' in neededSLAVES:     # remove EC2_boxes found in running from existing
                    if name in neededSLAVES['running']: # name found in collection of nodes used for building
                        break
                if atype in tagMain[jenkinsKey]:   #found and not being used for building
                    if atype in totalFound:
                        totalFound[atype].append(inst)
                    else:
                        totalFound.update({ atype:[inst]  })
                    break

        #pools=2
        #agentsNeeded ={}
        agentsNeeded =[]
        totalNewAgents=0
        agentReference={}
        p = mp.Pool()
        m = mp.Manager()
        q = m.Queue()
        #totalNeeded = needed + waiting_reserves
        toAddType={}
        d_agents=dict( [ag['type'],ag] for ag in defined_agents )
        if len(totalFound)>0:
            for atype in agent_Types:
                tfound = len(totalFound[atype])
                totalNeeded = neededSLAVES[atype] if atype in neededSLAVES else 0 + waiting_reserves
                tdiff = tfound -totalNeeded
                eInstances = totalFound[atype]
                if tdiff>0 :  ## too many agents.... get rid of some
                    running=0
                    instanceCommited=[]
                    DELETE =tdiff
                    for eID in eInstances:
                        if DELETE==0:
                            break
                        item =self.resource.Instance(eID['InstanceId'])
                        launchTime = item.launch_time
                        #####    LET's GET OUR MONEY's WORTH    #####
                        if (now_utc - launchTime).total_seconds() / 60 > run_time_mins:  ##happened 50mins ago
                            if  eID['Spot'] or not spot_enabled:  ## NOT ON DEMAND instance so DO terminate
                                self.nodeDelete(eID['InstanceId'],atype)
                                self.result['removed'] = self.result['removed'].append({'id':eID, 'tags':item.tags, 'label':atype})
                                item.terminate()
                                DELETE=DELETE-1
                        else:
                            running = running + 1
                        instanceCommited.append(eID)

                    #toRun=eInstances[waiting_reserves:]
                    WAIT = waiting_reserves
                    for eID in eInstances:  #set node to stop and disable  #ONLY ON DEMAND ALLOWED HERE
                        if WAIT==0:
                            break
                        item = self.resource.Instance(eID['InstanceId'])
                        launchTime = item.launch_time
                        #####    LET's GET OUR MONEY's WORTH    #####
                        if (now_utc - launchTime).total_seconds() / 60 > run_time_mins:  ##happened 50mins ago
                            if not eID['Spot']: # ONLY STOP ON DEMAND...
                                item.stop()
                                self.result['stopped'] = self.result['stopped'].append(
                                            {'id':eID['InstanceId'], 'tags':item.tags, 'label':atype})
                                WAIT=WAIT-1
                        else:
                            running = running + 1
                        instanceCommited.append(eID)

                    # LOOP throught NON - COMMITED instances and start as needed
                    for eInst in eInstances:  ## START stopped ON DEMAND FOUND
                        item = self.resource.Instance(eInst['InstanceId'])
                        if eInst not in instanceCommited:  #on demand only
                            if eInst['Spot'] or running >= totalNeeded: #can't start SPOT instances ....soo skip
                                continue
                            eInst.start()  #should be running...
                            running = running +1
                            self.result['started'] = self.result['started'].append(
                                            {'id': eID['InstanceId'], 'tags': item.tags, 'label': atype})

                elif tdiff<0:  ## not enough agents  .. add some use buffer
                    toAdd= math.fabs(tdiff)
                    agentReference.update({atype:self.nodeDefine(atype,d_agents[atype], waiting_reserves)})
                    totalNewAgents=toAdd+totalNewAgents
                    toAddType[atype]=toAdd
                    for t in range(toAdd):
                        agentsNeeded.append(atype)
                    #agentsNeeded.update{atype:toAdd}
                    #ec2_newList=self.nodeCreate(atype, defined_agents, toAdd)
        elif waiting_reserves>0:   # no new agents found... check waiting requirements if more than 0
            for atype in agent_Types:
                toAddType[atype] = totalNewAgents = toAdd = 1
                agentReference.update({atype: self.nodeDefine(atype, d_agents[atype], waiting_reserves)})
                for t in range(toAdd):
                    agentsNeeded.append(atype)
        countReserve=0
        ## CREATE NEW INSTANCES BELOW....
        waiting_types={}
        for agentLbl in agentsNeeded:
            reserve=False  #all reserves need to be on demand instances... so make sure they're FIRST
            if atype not in waiting_types:
                waiting_types.update({atype: agentReference[atype].waiting_reserves})
                if agentReference[atype].waiting_reserves > 0:
                    reserve = True
            elif waiting_types[atype] >= 0:
                waiting_types[atype] = waiting_types[atype] - 1
                reserve = True
            if totalNewAgents > 1:  # use Multi-thread
                #stopped = True if countReserve<toAddType[agentLbl] else False
                #countReserve=countReserve+1
                #reserve=False

                slave = p.apply_async( node_instantiate,(agentLbl,agentReference[atype],q, reserve) )
            else:
                slaves, warn = node_instantiate(agentLbl,agentReference[atype], None, reserve)
                self.result['started'] = self.result['started'] + slaves
                self.result['warn'] = self.result['warn'] + warn

        if totalNewAgents > 1:
            p.close()
            p.join()
            while not q.empty():
                ec2List,warn=q.get()
                self.result['started'] = self.result['started'] + ec2List
                self.result['warn'] = self.result['warn'] + warn




    def nodeDefine(self,label, adefined, waiting_reserves):
        ec2_SubnetId = adefined['vpc_subnet_id']
        subnet = self.resource.Subnet(ec2_SubnetId)
        zone = subnet.availability_zone
        user=self.module.params.get('user')
        userData = adefined['user_data'] if 'user_data' in adefined else None
        agent = type('obj', (object,), {
            'ec2_ami': adefined['ami'],
            'ec2_SecurityGroupIds': adefined['group_id'],
            'ec2_type': adefined['instance_type'],
            'ec2_spot_price': adefined['spot_price'],
            'ec2_SubnetId': adefined['vpc_subnet_id'],
            'os': adefined['os'],
            'userdata': userData,
            'user': user,
            'waiting_reserves': waiting_reserves,
            'cc': adefined['cc_jobs'],
            'zone': zone,
            'pName': self.profile,
            'keyName': self.module.params.get('tag_key'),
            'mRegion': self.module.params.get('region'),
            'spot_enabled': self.spot_enabled,
            'volumeGB': adefined['volumeGB'],
            'ec2_name': adefined['name'],
            'exclusive': adefined['exclusive'],
            'remoteFS': adefined['remoteFS'],
            'launcher': adefined['launcher'],
            'launcher_params': adefined['launcher_params'],
        }
                       )
        return agent


    def nodeDelete(self, instanceID, label):
        name="%s_%s"%(label, instanceID)
        self.server.delete_node(name)




class EC2Connector():
    def __init__(self, module, sts_client):
        self.access_key = module.params.get('aws_access_key')
        self.secret_key = module.params.get('aws_secret_key')
        self.security_token = module.params.get('security_token')
        self._region = module.params.get('region')
        self._resources = {}
        self._clients = {}
        self._sts_client = sts_client
        self.validate_certs = module.params.get('validate_certs')
        self._session = None

    @staticmethod
    def stsClient():
        return boto3.client('sts')
    def session_connect(self):
        boto3.client('ec2')


    def __get_resource__(self, service=""):
        if service not in self._resources:
            self._resources[service] = self._session.resource(service_name=service, region_name=self._region)
        return self._resources[service]

    def __get_client__(self, service=""):
        #print service
        if service not in self._clients:
            self._clients[service] = self._session.client(service_name=service, region_name=self._region)
        return self._clients[service]

    def connect(self):
        self._session = self.sessionDefault() if self.security_token is None else self.sessionCreate()

    def sessionCreate(self):
        self._session = boto3.Session(aws_access_key_id=self.access_key,
                                aws_secret_access_key= self.secret_key,
                                aws_session_token=self.security_token)
        return self._session

    def sessionDefault(self):
        self._session = boto3._get_default_session()
        return self._session





def agentRegister( name, eID,label, remoteFS, exclusive,cc, launcher, params):
    global jenkinsAgent
    jenkinsAgent.server.create_node(
        name,
        nodeDescription='Ansible slave %s for label:%s' % (eID, label),
        remoteFS=remoteFS,
        numExecutors=cc,
        labels=label,
        exclusive=exclusive,
        launcher=str(getattr(jenkins, launcher)),
        launcher_params=params   )
    # jenkins.LAUNCHER_COMMAND, jenkins.LAUNCHER_SSH, jenkins.LAUNCHER_JNLP,
    # jenkins.LAUNCHER_WINDOWS_SERVICE

def node_instantiate(label, agentObject, que=None, isReserve=False):

    global ARG_SPEC
    warn=[]
    argument_spec = copy.copy(ARG_SPEC)
    waiting_reserves = agentObject.waiting_reserves
    try:
        sts = EC2Connector.stsClient()
        cc=EC2Connector(argument_spec, sts)
        cc.connect()

    except botocore.exceptions.ClientError as e:
            module.fail_json(msg="Can't authorize [threadded] connection - {0}".format(e))

    resource = cc.__get_resource__('ec2')
    client = cc.__get_client__('ec2')

    needed=1
    if agentObject.volumeGB > 0:
        #print '....spot requested at price: %s' % agentObject.ec2_spot_price
        blockMap = [{
            'DeviceName': '/dev/sda1',
            'Ebs': {
                'VolumeSize': agentObject.volumeGB,
                'DeleteOnTermination': True,
            },
        },
        ]
    if agentObject.userdata:
        userDATA = agentObject.userdata
    elif agentObject.os=='linux':
        userDATA =  "#!/bin/bash \n yum install aws-cli -y \n INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)\n \n aws ec2 create-tags --region %s  --resources $INSTANCE_ID --tags Key=Name,Value=%s Key=%s,Value=%s  Key=%s,Value=%s" % (agentObject.mRegion,
                    agentObject.ec2_name, agentObject.keyName, label, 'DIVISION', 'cd')
    if agentObject.ec2_spot_price > 0 and not isReserve:
        launchSpec = {
            'ImageId': agentObject.ec2_ami,
            'InstanceType': agentObject.ec2_type,
            'UserData': base64.b64encode(userDATA),
            'Placement': {
                'AvailabilityZone': '%s' % (agentObject.zone),
            },

            # 'EbsOptimized': True,
            'Monitoring': {
                'Enabled': True
            },
            'SubnetId': agentObject.ec2_SubnetId,
            'IamInstanceProfile': {
                'Name': agentObject.pName
            },
            'SecurityGroupIds': [
                agentObject.ec2_SecurityGroupIds,
            ]
        }
        if len(blockMap) > 0:
            launchSpec.update({'BlockDeviceMappings': blockMap})

        warn.append(" adding the count to : %s"%needed)
        warn.append(" ....launchSpec %s"%launchSpec)
        ec2in = client.request_spot_instances(
            DryRun=False,
            SpotPrice=str(agentObject.ec2_spot_price),
            #ClientToken='string',  IF YOU LEAVE THIS NO additional spot instances will be created
            InstanceCount=needed,
            Type='one-time',
            LaunchSpecification=launchSpec
        )

        spot_label='%s_%s'%('spot',label)
        ec2_list = []
        request_list=[]
        #raise ValueError(ec2in)
        # instance = reservation.instances[0]
        for inst in ec2in['SpotInstanceRequests']:
            #won't be here YET  get the request ID first
            #eID = inst['InstanceId']
            rID = inst['SpotInstanceRequestId']
            # print('Tagging spot request.')
            while True:
                try:
                    client.create_tags(Resources=[rID], Tags=[
                                {'Key': 'Name', 'Value': '%s-%s'%(spot_label, agentObject.ec2_name) },
                                {'Key': agentObject.keyName, 'Value': spot_label },
                                {'Key': 'DIVISION', 'Value': 'cd' } ]
                        )
                except:
                    pass
                else:
                    break

            request_list.append(rID)
        time.sleep(2)
        ec2requests = client.describe_spot_instance_requests(SpotInstanceRequestIds=request_list)['SpotInstanceRequests']
        warn.append(ec2requests)
        #raise ValueError(ec2requests)


        ec2_list=spot_waitingRequest(client,resource,request_list,spot_label, agentObject)
        if  not agentObject.userdata and len(ec2_list)>0:
            ec2IDs = [ ee['eid'] for ee in ec2_list]
            response = client.create_tags(DryRun=False, Resources=ec2IDs,
                Tags=[ {'Key': agentObject.keyName, 'Value': spot_label },  {'Key': 'DIVISION', 'Value': 'cd' },
                            ]
            )
        #raise ValueError(ec2_list)
    else:
        #print '....standard ec2 ondemand tyep: %s' % agentObject.ec2_type
        ec2_array = resource.create_instances(
            # Use the official ECS image
            ImageId=agentObject.ec2_ami,
            MinCount=needed,
            MaxCount=needed,
            BlockDeviceMappings=blockMap,
            SubnetId=agentObject.ec2_SubnetId,
            SecurityGroupIds=[
                agentObject.ec2_SecurityGroupIds,
            ],
            InstanceType=agentObject.ec2_type,
            IamInstanceProfile={
                "Name": agentObject.pName
            },
            UserData=userDATA
            # UserData="#!/bin/bash \n echo ECS_CLUSTER=" + cluster_name + " >> /etc/ecs/ecs.config"
        )
        ec2_list=[]
        for inst in ec2_array:
            iagent = inst
            eID = iagent.id
            ec2_list.append({'InstanceId':eID })
            #inst = copy.copy(instance.meta.data)
            iagent.wait_until_running()
            name = "%s_%s" % (label, eID)
            agentRegister( name, eID, label, agentObject.remoteFS, agentObject.exclusive, agentObject.cc, agentObject.launcher, agentObject.launcher_params)

        if not agentObject.userdata:
            ec2IDs = [ inst.id for inst in ec2_list]
            response = client.create_tags(
                DryRun=True | False,
                Resources=ec2IDs,
                Tags=[{'Key': agentObject.keyName, 'Value': label}, {'Key': 'DIVISION', 'Value': 'cd'},
                      ]
            )
    if que is not None:
        que.put((ec2_list,warn))

    return ec2_list,warn

def spot_waitingRequest(client,resource,request_list,label, agentObject):
    ec2requests = client.describe_spot_instance_requests(SpotInstanceRequestIds=request_list)
    ec2_list=[]
    for rq in ec2requests['SpotInstanceRequests']:
        state = rq['State']
        if 'open' in rq['State']:
            time.sleep(2 if agentObject.os=='linux' else 30)
            list=spot_waitingRequest(client,resource,request_list,label, agentObject)
            return list
        if 'active' in rq['State']:
            price = rq['SpotPrice']
            rc=resource.Instance(rq['InstanceId'])
            rc.wait_until_running()
            #statein='active'
            ec2_list.append({'eid':rq['InstanceId'],'price':price})

    for ec2 in ec2_list:
        name = "%s_%s" % (label, ec2['eid'])
        agentRegister(name, ec2['eid'], label, agentObject.remoteFS, agentObject.exclusive, agentObject.cc, agentObject.launcher,
                  agentObject.launcher_params)
    return ec2_list


def test_dependencies(module):
    if not HAS_BOTO3:
        module.fail_json(msg='boto3 is required for this module.')
    if not python_jenkins_installed:
        module.fail_json(msg="python-jenkins required for this module. "\
              "see http://python-jenkins.readthedocs.io/en/latest/install.html")

    if not python_lxml_installed:
        module.fail_json(msg="lxml required for this module. "\
              "see http://lxml.de/installation.html")


def job_config_to_string(xml_str):
    return ET.tostring(ET.fromstring(xml_str))

def main():
    global ARG_SPEC, module
    argument_spec = ec2_argument_spec()

    argument_spec.update(dict(
      tag_key=dict(required=True, default=None),
      tag=dict(required=True, default=None),
      region=dict(required=True, default=None),
      aws_access_key=dict(required=True, default=None),
      security_token=dict(required=True, default=None, no_log=True),
      roleUsed=dict(required=True, default=None),
      mins_toStop=dict(required=True, default=None, type='int'),
      profile_ec2=dict(required=True, default=None),
      facts=dict(required=True, default=None,type='dict'),
      agents=dict(required=True, default=None,type='list'),
      waiting_reserve=dict(required=False, default=1),
      password=dict(required=False, no_log=True),
      token=dict(required=False, no_log=True),
      url=dict(required=False, default="http://localhost:8080"),
      spot_enabled=dict(required=False, default=False),
      user=dict(required=False)

        #    spot_enabled: "{{ project.jenkins.spot_enabled }}"
      )
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True,
                           required_together=[['facts','agents']],
                        mutually_exclusive=[['password', 'token']],
                    )
    test_dependencies(module)
    # validate dependencies

    try:
        region, endpoint, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
        aws_connect_kwargs.update(dict(region=region,
                                     endpoint=endpoint,
                                     conn_type='both',
                                     resource='ec2'
                                     ))
        #ec2_connect()
        #module.fail_json(msg=" dude;;;;  {0}".format(ARG_SPEC) )

        #ARG_SPEC = moduleEC2_obj(module)
        ARG_SPEC = module
        #module.fail_json(msg=" dude;;;;  {0}".format(ARG_SPEC) )
        if not region:
            module.fail_json(msg="Region must be specified as a parameter, in EC2_REGION or AWS_REGION environment variables or in boto configuration file")
            #ecr = boto3_conn(module, conn_type='client', resource='ecr', region=region, endpoint=endpoint, **aws_connect_kwargs)
        client,resource = boto3_conn(module, **aws_connect_kwargs)
    except botocore.exceptions.ClientError as e:
            module.fail_json(msg="Can't authorize connection - {0}".format(e))
    except Exception as e:
            module.fail_json(msg="Connection Error - {0}".format(e))

    jenkins_agents=JenkinsAgent(module,client,resource)

    result = jenkins_agents.slaveDistribute()

    module.exit_json(**result)


def moduleEC2_obj(module):
    obj = type('obj', (object,), {
        'access': module.params.get['aws_access_key'],
        'secret': module.params.get['aws_secret_key'],
        'token': module.params.get['security_token'],
        'region': module.params.get['region'],
        'validate_certs': module.params.get['validate_certs']
    }
                   )
    return obj
# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()

