#!/usr/bin/python


DOCUMENTATION = '''
---
module: cd_ecs_compose
short_description: converts composer file into ansible dict for modules.
description:
    - This module allows the user to converts compose file for docker into ansible dict for modules..
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
  cluster_list:
    description:
      - list of clusters services and tasks.
    required: true
    default: null
    aliases: []
    type: 'list'
'''

EXAMPLES = '''
- name: list KMS keys
  cd_ecs_compose:
    cluster_list: [{}]
  register: composeDict
'''

from collections import defaultdict

import os
import copy
import __builtin__
try:
    import yaml
    import json
    has_lib_yaml = True
except ImportError:
    has_lib_yaml = False

##ec2_model = type('obj', (object,), {'name': exp['owner'], 'regx': exp[(svc)]['rx'], 'svc':svc})
ec2_keys = {'cpu':'int',
            'memory':'int',
            'essential':'bool',
            'image':'str',
            'mountPoints':'list',
            'links':'list',
            'portMappings':'list',
            'volumesFrom':'int',
            'command':'list',
            'entryPoint':'list',
            'container_name':'str'
            }
##  name, image, cpu, memory, memoryReservation, links, portMappings, essential, entryPoint, command, environment, mountPoints, volumesFrom, hostname, user, workingDirectory, disableNetworking, privileged, readonlyRootFilesystem, dnsServers, dnsSearchDomains, extraHosts, dockerSecurityOptions, dockerLabels, ulimits, logConfiguration
ec2Lower= dict((k.lower(), k) for k,v in ec2_keys.items())

def compose(module, clusters):
    tasks = []
    tasks_containers=[]
    svcs=[]
    vlms=[]
    svc_tsks=[]
    warn=[]
    for c in clusters:
        for s in c['services']:
            clusterName= c['name']
            task = s['task_definition']
            s.update({'cluster':clusterName})
            svcs.append(s)
            svc_tsks.append(task.split(':')[0])
        for tsk in c['tasks']:
            tasq = copy.copy(tsk)
            dictIN, lost = compose2yaml(module,tasq,tasq['compose_file'])
            warn.append({tsk['name']:lost})
            tasq.update({'containers':dictIN})
            tasks_containers.append(tasq)
            if tsk['name'] not in svc_tsks:
                tsk.update({'cluster':clusterName})
                tasks.append(tsk)
            #if len(lost)>0:
            #    print('\n%s' % module.jsonify({'msg': "Warn: [ECS] following properties not found %s"%(lost)}))

    return {'tasks':tasks, 'volumes':vlms, 'services':svcs,'containers':tasks_containers, 'missing':warn}

def compose2yaml(module,task,composefile):
    fullpath = os.path.expandvars(os.path.expanduser(composefile))
    with open(fullpath, newline='') as stream:
        data = yaml.load(stream)
    aObj=[]
    lostkeys=[]
    for key,value in data.items():
        container = {'name':key}
        container.update({'memory':task['memory']})
        for k,v in value.items():
            lkey= k.lower()
            if lkey in ec2Lower:
                keyIN =ec2Lower[lkey]
                vlu = getattr(__builtin__, ec2_keys[keyIN]) ( v )
                if 'container_name' in lkey:
                    container.update( {'name':vlu } )
                else:
                    container.update( {keyIN:vlu} )
            elif lkey in 'ports':  # list for values need to be broken up
                ports=[]
                for p in v:
                    pSplit = p.split(":")
                    #print('\n%s' % module.jsonify({'msg': "Warn: [ECS] pSplit %s" % (pSplit)}))
                    ports.append({'containerPort':int(pSplit[0]),'hostPort':int(pSplit[1])  })
                container.update({'portMappings': ports})
            elif lkey in 'command':
                container.update({'command': list(v)})
            elif lkey in 'volumes':
                volumes = []
                for p in v:
                    vSplit = p.split(":")
                    ports.append({'containerPath': vSplit[0], 'sourceVolume': vSplit[1]})
                container.update({lkey: volumes})
            else:
                lostkeys.append(k)
        aObj.append(container)
    return aObj, lostkeys






def main():
    module = AnsibleModule(
        argument_spec = dict(
            cluster_list        = dict(required=True, type='list')),
        required_together = ([] ),
        supports_check_mode = True,
    )

    if not has_lib_yaml:
        module.fail_json(msg="YAML required for this module")

    cluster_list = module.params.get('cluster_list')

    if not cluster_list:
        module.fail_json(msg="'%s' is an unknown value for the cluster_list argument" % cluster_list)

    resultpy = compose(module,cluster_list)

    module.exit_json(changed=True, result=resultpy)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.pycompat24 import get_exception


if __name__ == '__main__':
    main()

