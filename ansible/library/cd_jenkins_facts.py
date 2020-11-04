#!/usr/bin/python


DOCUMENTATION = '''
---
module: cd_jenkins_facts
short_description: provide dict with list of jobs,nodes/agent, queue and builds/building
description:
    - list of Jobs,Agents,Builds and Queues by using Jenkins REST API.
requirements:
  - "python-jenkins >= 0.4.12"
  - "lxml >= 3.3.3"
version_added: "2.2"
author: "Robert Colvin"
options:
  name:
    description:
      - Name of the Jenkins job.
    required: false
  name:
    description:
      - Name of the Jenkins job.
    required: false
  password:
    description:
      - Password to authenticate with the Jenkins server.
    required: false
  state:
    description:
      - Attribute that specifies if the job has to be created or deleted.
    required: false
    default: present
    choices: ['present', 'absent']
  token:
    description:
      - API token used to authenticate alternatively to password.
    required: false
  url:
    description:
      - Url where the Jenkins server is accessible.
    required: false
    default: http://localhost:8080
  user:
    description:
       - User to authenticate with the Jenkins server.
    required: false
'''

EXAMPLES = '''
# Create a jenkins job using basic authentication
- jenkins_job:
    config: "{{ lookup('file', 'templates/test.xml') }}"
    name: test
    password: admin
    url: http://localhost:8080
    user: admin

# Create a jenkins job using the token
- jenkins_job:
    config: "{{ lookup('template', 'templates/test.xml.j2') }}"
    name: test
    token: asdfasfasfasdfasdfadfasfasdfasdfc
    url: http://localhost:8080
    user: admin

# Delete a jenkins job using basic authentication
- jenkins_job:
    name: test
    password: admin
    state: absent
    url: http://localhost:8080
    user: admin

# Delete a jenkins job using the token
- jenkins_job:
    name: test
    token: asdfasfasfasdfasdfadfasfasdfasdfc
    state: absent
    url: http://localhost:8080
    user: admin

# Disable a jenkins job using basic authentication
- jenkins_job:
    name: test
    password: admin
    enabled: False
    url: http://localhost:8080
    user: admin

# Disable a jenkins job using the token
- jenkins_job:
    name: test
    token: asdfasfasfasdfasdfadfasfasdfasdfc
    enabled: False
    url: http://localhost:8080
    user: admin
'''

RETURN = '''
---
name:
  description: Name of the jenkins job.
  returned: success
  type: string
  sample: test-job
state:
  description: State of the jenkins job.
  returned: success
  type: string
  sample: present
enabled:
  description: Whether the jenkins job is enabled or not.
  returned: success
  type: bool
  sample: true
user:
  description: User used for authentication.
  returned: success
  type: string
  sample: admin
url:
  description: Url to connect to the Jenkins server.
  returned: success
  type: string
  sample: https://jenkins.mydomain.com
'''

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


class JenkinsFact:
    def __init__(self, module):
        self.module = module

        self.name = module.params.get('name')
        self.type = module.params.get('type')
        self.password = module.params.get('password')
        self.token = module.params.get('token')
        self.user = module.params.get('user')
        self.jenkins_url = module.params.get('url')
        self.server = self.get_jenkins_connection()

        self.result = {
            'changed': False,
            'url': self.jenkins_url,
            'name': self.name,
            'user': self.user,
            'jobs': [],
            'nodes':[],
            'queues':[],
            'building':[]
        }

        # This kind of jobs do not have a property that makes them enabled/disabled
        self.job_classes_exceptions = ["jenkins.branch.OrganizationFolder"]

        self.EXCL_STATE = "excluded state"

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



    def get_agent(self):
        #[{'offline': False, 'name': u'master'}, {'offline': False, 'name': u'win-pci-agent-1'}, {'offline': False, 'name': u'win-redgate-agent-1'}, {'offline': False, 'name': u'windows-agent-1'}, {'offline': True, 'name': u'windows-agent-aws-golden-dev-test-1'}, {'offline': False, 'name': u'windows-agent-aws-golden-stg-prod-1'}]

        #[{'offline': False, 'name': u'master'}, {'offline': False, 'name': u'win-pci-agent-1'}, {'offline': False, 'name': u'win-redgate-agent-1'}, {'offline': False, 'name': u'windows-agent-1'}, {'offline': False, 'name': u'windows-agent-aws-golden-dev-test-1'}, {'offline': False, 'name': u'windows-agent-aws-golden-stg-prod-1'}]
        if self.name is None:
            return self.server.get_nodes()
        else:  ## get build given by name
#{u'numExecutors': 4, u'displayName': u'windows-agent-aws-golden-stg-prod-1', u'manualLaunchAllowed': True, u'executors': [{}, {}, {}, {}], u'monitorData': {u'hudson.node_monitors.SwapSpaceMonitor': {u'totalPhysicalMemory': 4294557696, u'availableSwapSpace': 8710963200, u'_class': u'hudson.node_monitors.SwapSpaceMonitor$MemoryUsage2', u'availablePhysicalMemory': 3517739008, u'totalSwapSpace': 9394831360}, u'hudson.node_monitors.ClockMonitor': {u'diff': 14, u'_class': u'hudson.util.ClockDifference'}, u'hudson.node_monitors.DiskSpaceMonitor': {u'size': 53426753536, u'timestamp': 1489178799019, u'_class': u'hudson.node_monitors.DiskSpaceMonitorDescriptor$DiskSpace', u'path': u'D:\\jenkins'}, u'hudson.node_monitors.TemporarySpaceMonitor': {u'size': 66583572480, u'timestamp': 1489178799195, u'_class': u'hudson.node_monitors.DiskSpaceMonitorDescriptor$DiskSpace', u'path': u'C:\\Windows\\Temp'}, u'hudson.node_monitors.ResponseTimeMonitor': {u'timestamp': 1489178799017, u'average': 51, u'_class': u'hudson.node_monitors.ResponseTimeMonitor$Data'}, u'hudson.node_monitors.ArchitectureMonitor': u'Windows NT (unknown) (x86)'}, u'loadStatistics': {u'_class': u'hudson.model.Label$1'}, u'iconClassName': u'icon-computer', u'actions': [], u'idle': True, u'oneOffExecutors': [], u'temporarilyOffline': False, u'offlineCause': None, u'launchSupported': False, u'_class': u'hudson.slaves.SlaveComputer', u'offlineCauseReason': u'', u'offline': False, u'jnlpAgent': True, u'icon': u'computer.png'}
            return [self.server.get_node_info(self.name)]


    def get_build(self):
        if self.name is None:

          #'executor': 1, 'name': u'ku-portal-git', 'number': 1}]
            return self.server.get_running_builds()
        else:  ## get build given by name
            return [self.server.get_build_info(self.name)]
    def get_queue(self):
        if self.name is None:
            
            return self.server.get_queue_info()
        else:  ## get build given by name
            return [self.server.get_queue_info(self.name)]
    def get_job(self):
        if self.name is None:
            return self.server.get_jobs()
        else:  ## get build given by name
            try:
                response = self.server.get_job_info(self.name)
                if self.job_class_excluded(response):
                    return self.EXCL_STATE
                else:
                    return response['color'].encode('utf-8')

            except Exception:
                e = get_exception()
                self.module.fail_json(msg='Unable to fetch job information, %s' % str(e))
    def get_jobs_total(self):
        return self.server.jobs_count()


    def get_result(self):
        result = self.result
        type = self.type
        if type=='node':
            nodes = self.get_agent()
            self.result['nodes']=nodes
        elif type=='queue':
            queues = self.get_queue()
            self.result['queues']=queues
        elif type=='job':
            jobs=self.get_job()
            self.result['jobs']=jobs
        elif type=='build':
            builds=self.get_build()
            self.result['building']=builds
        elif type=='all':
            nodes = self.get_agent()
            queues = self.get_queue()
            jobs=self.get_job()
            builds=self.get_build()
            self.result['nodes']=nodes
            self.result['queues']=queues
            self.result['jobs']=jobs
            self.result['building']=builds
        return result

    def nodeLabels(self, node_str):
        n = self.server.get_node(node_str)
        response = n.jenkins.requester.get_and_confirm_status("%(baseurl)s/config.xml" % n.__dict__)
        _element_tree = ET.fromstring(response.text)
        node_labels = _element_tree.find('label').text


def test_dependencies(module):
    if not python_jenkins_installed:
        module.fail_json(msg="python-jenkins required for this module. "\
              "see http://python-jenkins.readthedocs.io/en/latest/install.html")

    if not python_lxml_installed:
        module.fail_json(msg="lxml required for this module. "\
              "see http://lxml.de/installation.html")


def job_config_to_string(xml_str):
    return ET.tostring(ET.fromstring(xml_str))

def main():

    module = AnsibleModule(
        argument_spec = dict(
            name        = dict(required=False, default=None),
            type        = dict(required=False, default=None, choices=['all','node','job','queue','build'] ),
            password    = dict(required=False, no_log=True),
            token       = dict(required=False, no_log=True),
            url         = dict(required=False, default="http://localhost:8080"),
            user        = dict(required=False)
        ),
        mutually_exclusive = [
            ['password', 'token'],
            ['config', 'enabled'],
        ],
        #required_together=[['limit','document']],
        supports_check_mode=True,
    )

    test_dependencies(module)
    jenkins_fact = JenkinsFact(module)
    nameIN = module.params.get('name')
    if nameIN is None:
        if module.params.get('type') is None:
            module.fail_json(msg='"type" required when using "name"  %s' % (str(nameIN ) ) )

    result = jenkins_fact.get_result()
    module.exit_json(**result)



from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()