#!/usr/bin/python

#/*
# * dynamodb utilities for ansible module tools
# */

DOCUMENTATION = '''
---
module: cd_dynamo_facts
short_description: get information about dynamoDB.
description:
    - This module allows the user to list information about dynamoDB on levels (region,table, document) . This module has a dependency on python-boto.
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
  table_name:
    description:
      - level='table' name will be used for table name.
    required: false
    default: null
    aliases: []
  document_limit:
    description:
      - Maximum number of documents to return.
    required: false
    default: 1
    type: 'int'
    choices: ['region','table','document']
  level:
    description:
      - Target level to read/print data structure.
    required: false
    default: region
    choices: ['region','table','document']
  key_filter:
    description:
      - Key/column of table to filter results.
    required: false
    default: null
    type: 'list'
  key_filter_value:
    description:
      - Value of given key filter.
    required: false
    default: null
    type: 'dict'
  dryrun:
    description:
      - updates values provided or just runs to present possible errors/warnings. opposite of  'change'
    required: false
    default: False
    type: 'bool'
  override:
    description:
      - updates/override existing values if found for given table. Set to False if you don't want to update with differences found in table definition.
    required: false
    default: False
    type: 'bool'
  output_file:
    description:
      - Value of given key filter.
    required: false
    default: null
  target_env_value:
    description:
      - Value of TARGET environment value found in CSV file .  ONLY required if csv file given for load_from most file look like this DEVELOPMENT : [141255817051] where 'DEVELOPMENT' would be the target title/target_env_value.
    required: false
    default: null
  output_type:
    description:
      - Value of given key filter.
    required: false
    default: null
    choices=['csv', 'json', 'yaml']
  format_output:
    description:
      - Value of given key filter.
    required: false
    default: null
    choices=['pipeline', 'log']
  recurse:
    description:
      - based on the level, recurse will pull all nested levels below selection. if level='table' recurse will describe the table properties AND pull records upto given limit.
    required: false
    default: false
    type: 'bool'
  target_data:
    description:
      - data that needs to be encrypted or decrypted. field requires action
    required: false
    default: null
'''

EXAMPLES = '''
- name: dynamo cd import DATA from FILE import all on level
  cd_dynamo_set:
    aws_access_key: "{{ access }}"
    aws_secret_key: "{{ secret }}"
    security_token: "{{ token }}"
    region: "{{ project.region }}"
    table_name: "{{ item.name }}"
    level: "{{ item.level }}"
    recurse: "{{ item.recurse }}"
    load_from: "{{ item.load_from }}"
    target_env_value: "{{ item.target_env_value }}"
    playbook_dir: '{{ playbook_dir }}'
  register: dynamoResults3
- name: Dynamodb file that represents tables in region
  cd_dynamo_facts:
    table_name: "Hello-World"
    level: "region"
    recurse: true
    output_file: "somefile"
    output_type: "json"
    load_from: "{{ item.load_from }}"
    playbook_dir: '{{ playbook_dir }}'
    target_env_value: "{{ item.target_env_value }}"
  register: result
- name: get specific records
  cd_dynamo_facts:
    table_name: "Hello-World"
    level: "document"
    recurse: true
    key_filter:
        - user_email
        - username
    key_filter_value:
        - user_email: bgarner@gmail.com
        - role: faculty
    document_limit: 1
    output_file: "somefile"
    output_type: "json"
    load_from: "{{ item.load_from }}"
    playbook_dir: '{{ playbook_dir }}'
    target_env_value: "{{ item.target_env_value }}"
  register: result
'''
#import sys
#sys.path.insert(0, '/path/to/application/app/folder')
import sys, os

#import FormaterGenerate, ProviderGenerate

from collections import defaultdict

#from dynamo_lib import FormaterGenerate, ProviderGenerate
#from dynamo_lib import auditMeth
auditMethIN=None
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
SERVICE='dynamodb'

def awsAccountID(module):
    global auditMethIN
    auditMeth = auditMethIN
    region, endpoint, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
    aws_connect_kwargs.update(dict(region=region,
                                   endpoint=endpoint,
                                   conn_type='client',
                                   resource='sts'
                                   ))

    client = boto3_conn(module, **aws_connect_kwargs)
    return client.get_caller_identity()["Account"]


max_Memory= None

def loadFile(module,formater,prvdr_name, path, Keylabel, KeyValue):
    mBytes = (512 if max_Memory is None else max_Memory) * 1000 * 1000
    # mBytes =5000
    file_size_max = mBytes * .6
    filePath, f = path.split(".")
    try:
        fmtr = formater.create(f.upper(), filePath, True)
    except e:
        if 'object is not callable':
            module.fail_json(msg="  [E] ERROR no extension formater found for   - {0}".format(f))
        else:
            module.fail_json(msg="  [E] loadFile  - {0}".format(e))


    fullpath = '%s.%s' % (fmtr._filepath, fmtr._extension)
    size = os.stat(fullpath).st_size
    if size > file_size_max and dPipeline == '':
        dataPipeline = True
        #print ('To BIG  reduce  %s' % (size))
        #print ('use data pipeline instead')
        return None
    acct = awsAccountID(module)
    envs={str(acct):{'all':'ansible', Keylabel:KeyValue}}
    try:
        dynoObj = fmtr.load( SERVICE, envs, Keylabel)
    except ValueError as err:
        module.fail_json(msg="  [E] loadFile  - {0}".format(err.args))
    return dynoObj

def cd_dynamo_region(module,prvdr,prvdr_name,formater,account,data):
    global auditMethIN
    auditMeth = auditMethIN
    limit = data['document_limit']
    path =  data['load_from']
    target_value=data['target_env_value']
    applyChanges=True if not data['dryrun'] else False
    override=True
    environment_Title = 'title'
    dynoObj = loadFile(module,formater, prvdr_name,path, environment_Title, target_value)
    objs, pyObj = prvdr.UpdateTables(dynoObj, target_value, applyChanges, override)
    return True, pyObj, objs

def cd_dynamo_table(module,prvdr,prvdr_name,formater,account,data):
    global auditMethIN
    auditMeth = auditMethIN
    pyObj={account:{'tables':{}}}
    limit = data['document_limit']
    path =  data['load_from']
    tableName=data['table_name']
    target_value=data['target_env_value']
    applyChanges=True if not data['dryrun'] else False
    override=True
    environment_Title = 'title'
    dynoObj = loadFile(module,formater, prvdr_name,path, environment_Title, target_value)
    objs, pyObj = prvdr.UpdateTable(dynoObj, target_value,tableName, applyChanges, override)
    return True, pyObj, objs



def cd_dynamo_document(module,prvdr,prvdr_name,formater,account,data):
    global auditMethIN
    auditMeth = auditMethIN
    pyObj={account:{'tables':{}}}
    limit = data['document_limit']
    path =  data['load_from']
    tableName=data['table_name']
    target_value=data['target_env_value']
    applyChanges=True if not data['dryrun'] else False
    override=True
    environment_Title = 'title'
    dynoObj = loadFile(module,formater, prvdr_name,path, environment_Title, target_value)
    objs, pyObj = prvdr.UpdateDocument(dynoObj, target_value,tableName, applyChanges, override)
    #module.fail_json(msg="  [E] document issue  - {0}".format(objs))
    return True, pyObj, objs



def main():
    global auditMethIN
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
      table_name=dict(required=False, default=None),
      state=dict(default='present', required=False, choices=['present', 'absent']),
      level=dict(required=False, default='region', choices=['region','table','document']),
      recurse=dict(required=False, default=False, type='bool'),
      dryrun=dict(required=False, default=False, type='bool'),
      document_limit=dict(required=False,default=5, type='int'),
      key_filter=dict(required=False, default=None,type='list'),
      key_filter_value=dict(required=False, default=None, type='dict'),
      threaded=dict(required=False, default=True),
      load_from=dict(required=True, default=None),
      target_env_value=dict(required=False, default=None),
      playbook_dir=dict(required=True, default=None),
      output_file=dict(required=False, default=None),
      output_type=dict(required=False, default=None, choices=['csv','json','yaml']),
      format_output=dict(required=False, default=None, choices=['pipeline','log']),
      crypto_table_keys=dict(required=False, default=None, type='list'),
      crypto_solution_keys=dict(required=False, default=None, type='list')
      )
    )

    choice_map={
      "region": cd_dynamo_region,
      "table": cd_dynamo_table,
      "document": cd_dynamo_document
    }

    module = AnsibleModule(
      argument_spec=argument_spec,
      supports_check_mode=True,
      mutually_exclusive=[['document','recurse'] ],
      required_together=[['output_file','output_type'],['limit','document']]
    )
    # validate dependencies
    if not HAS_BOTO3:
        module.fail_json(msg='boto3 is required for this module.')

    #file_args=module.load_file_common_arguments(module.params)

    #module.fail_json(msg="...........checking file path  - {0}".format(module.params['playbook_dir']))
    _dlib_path = '%s/%s'%(module.params['playbook_dir'],'library/dynamo_lib' )

    sys.path.append(os.path.abspath(os.path.dirname(_dlib_path)))
    from dynamo_lib import FormaterGenerate
    from dynamo_lib import ProviderGenerate
    from dynamo_lib import auditMeth
    auditMethIN = auditMeth
    svc='dynamodb'
    try:
        region, endpoint, aws_connect_kwargs = get_aws_connection_info( module, boto3=True )
        aws_connect_kwargs.update(dict(   region=region, endpoint=endpoint,
                                        conn_type='both',
                                        resource=svc
                                     ) )
        if module.params.get('key_filter') and module.param.get('level') != 'document':
          module.fail_json( msg='level needs to be set to "document" when using key_filter')
        if module.params.get('load_from'):
            extension = module.params.get('load_from').split(".")[1].upper()
            if "CSV" in extension:
                if 'target_env_value' not in module.params:
                    module.fail_json(msg=" Loading CSV file requires  target_env_value like 'DEVELOPMENT' for 'title' label - ")



        #client = boto3_conn(module, **aws_connect_kwargs)
        client,resource = boto3_conn(module, **aws_connect_kwargs)
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg="Can't authorize connection - {0}".format(e))
    except Exception as e:
        if "Unknown service: '%s"%(svc) in str(e):
            module.fail_json(msg="[E] Ansible module broken UPDATE EC2 swap client w/ resource {0}".format(e))
        else:
            module.fail_json(msg="Connection Error - {0}".format(e))


    acct = awsAccountID(module)
    session = None
    threaded = module.params.get('threaded')
    provider = ProviderGenerate()
    formater = FormaterGenerate()
    prvdr_name='JuxtaDynamo'
    prvdr = provider.simulate(prvdr_name, region, acct, client, resource, threaded, True)

    #prvdr = provider.create('JuxtaDynamo', accnt, session)  //used to enter data
    prvdr._setRecursive(module.params.get('recurse'))

    has_changed, resultpy, resultobj = choice_map.get(module.params['level'])(module, prvdr,prvdr_name, formater, acct, module.params )

    if module.params.get('state') == 'absent':
        module.fail_json(msg=" [W] state can only be present...if you need to modify/create or delete please do so within an import file using CSV, JSON or YAML")
    #module.fail_json(msg="        [E]       test test test...  - {0}".format(has_changed))

    if module.params.get('output_file'):
        output_type = module.params.get('output_type')
        filePath = module.params.get('output_file')
        if module.params.get('format_output'):
            format = module.params.get('format_output')
            if format == 'log':
                module.fail_json(msg="..log not ready.. BBBB")
                #print 'converts into line by line record entry using each file as a table'
        else:
            fmtr = formater.create(output_type.upper(), filePath, True)
            final_path=fmtr.write(resultobj if output_type == 'csv' else resultpy)
            #module.fail_json(msg="formater BBBB... Error - {0}".format(final_path) )

    if acct in resultpy:  #remove the extra account information here
        resultpy=resultpy[acct]
    #module.fail_json(msg="formater BBBB... Error - {0}".format(resultpy) )
    module.exit_json( changed=has_changed, result=None )
  


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *
from ansible.plugins.lookup import LookupBase
#from ansible.vars import hostvars

#sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/dynamo_lib'))

from collections import defaultdict


if __name__ == '__main__':
    main()

