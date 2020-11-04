#!/usr/bin/python
# (c) 2020, Robert Colvin <rcolvinemail@gmail.com>
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

from ansible.module_utils.ec2 import *
from ansible.module_utils.basic import *
import sys
import copy
import json
from hashlib import md5

try:
    import boto3
    from botocore.exceptions import ClientError, ParamValidationError, MissingParametersError
    HAS_BOTO3 = True
except ImportError:
    import boto              # seems to be needed for ansible.module_utils
    HAS_BOTO3 = False


DOCUMENTATION = '''
---
module: cd_lambda_invoke
short_description: invokes AWS Lambda function with payload.
description:
    - This module allows the invocation of AWS Lambda function from payload events such as S3 bucket
      events, DynamoDB and Kinesis streaming events via the Ansible framework.
      It is idempotent and supports "Check" mode.  Use module M(lambda) to manage the lambda
      function itself and M(lambda_alias) to manage function aliases.
version_added: "2.1"
author: Robert Colvin (@astro44)
options:
  lambda_function_arn:
    description:
      - The name or ARN of the lambda function.
    required: true
    aliases: ['function_name', 'function_arn']
  assert_key: key expected from lambda return obj
  assert_value: string to compare
  environ_override:
    description:
      -  object of key value pairs to replace existing values.
  payload:
    description:
      -  the event payload in question.
    required: true
requirements:
    - boto3
extends_documentation_fragment:
    - aws

'''

EXAMPLES = '''
---
# Simple example that invokes a Lambda from notification on an S3 bucket
  - name: Lambda invoke from s3 for preview
    lambda_event:
      event_source: s3
      function_name: Lambda-ui-baa-file-more-
      assert_key: success
      assert_value: true
      payload: {{somefile.yaml}}
      environ_override:
        v1_path: fdasfdsa/fdss
        v2_path: fdafdsafdsa/fdg

'''

RETURN = '''
---
lambda_s3_events:
    description: list of dictionaries returned by the API describing S3 event mappings
    returned: success
    type: list


'''

# ---------------------------------------------------------------------------------------------------
#
#   Helper Functions & classes
#
# ---------------------------------------------------------------------------------------------------


def lambda_exists(module, client, name):
    response = None
    try:
        response = client.get_function(FunctionName=name)
    except ClientError as e:
        module.fail_json(msg='Lambda[%s] doesnt exist %s' % (name, e))
    return response


def lambda_invoke(module, name, client, payload, type_in, function_keys):
    response = None
    try:
        response = client.invoke(
            FunctionName=name, InvocationType=type_in, Payload=payload)
    except ClientError as e:
        lambda_environ(module, client, name, function_keys['Environment'])
        module.fail_json(msg='Lambda[%s] failed to executed %s' % (name, e))
    return response


def cd_invoke(module, client, name, payload, type_in, assert_key=None, assert_result=None, timeout=None, environ_override=None):
    found = False
    result = None
    function_keys = lambda_exists(module, client, name)[
        'Configuration']['Environment']
    if environ_override:
        lambda_environ(module, client, name, environ_override, function_keys)
    result = lambda_invoke(module, name, client,
                           payload, type_in, function_keys)
    if environ_override:
        lambda_environ(module, client, name, function_keys)
    if assert_key:
        if assert_key in result:
            if result[assert_key] == assert_result:
                found = True
    elif result:
        found = True
    if found:
        module.fail_json(msg='Lambda[%s] failed assert of %s:%s failed' % (
            name, assert_key, assert_result))
    return [name], False if found else True


def lambda_environ(module, client, name, environ_override, function_keys=None):
    response = None
    try:
        if function_keys:
            env = copy.deepcopy(function_keys)
            env['Variables'].update(environ_override)
        else:
            if 'Variables' in environ_override:
                env = environ_override
            else:
                env = {'Variables': environ_override}
        response = client.update_function_configuration(
            FunctionName=name, Environment=env)
    except ClientError as e:
        if function_keys:
            lambda_environ(module, client, name, function_keys['Environment'])
        module.fail_json(msg='Lambda[%s] ENV update failed %s' % (name, e))
        module.fail_json(msg='Lambda[%s] ENV update failed' % (name))
    return response

# ---------------------------------------------------------------------------------------------------
#
#   MAIN
#
# ---------------------------------------------------------------------------------------------------


def main():
    """
    Main entry point.

    :return dict: ansible facts
    """

    # produce a list of function suffixes which handle lambda events.
    this_module = sys.modules[__name__]
    source_choices = [function.split(
        '_')[-1] for function in dir(this_module) if function.startswith('lambda_event')]

    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        function_name=dict(required=True, default=None, type='str'),
        payload=dict(required=True, default=None, type='str'),
        invocation_type=dict(required=False, default='Event', choices=[
                             'Event', 'RequestResponse', 'DryRun']),
        timeout=dict(required=False, default=None, type='int'),
        assert_key=dict(required=False, default=None, type='str'),
        assert_result=dict(default=False, required=False),
        environment_variables=dict(default=None, required=False, type='dict'),
    )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=[],
        required_together=[]
    )
    # validate dependencies
    if not HAS_BOTO3:
        module.fail_json(msg='boto3 is required for this module.')
    try:
        region, endpoint, aws_connect_kwargs = get_aws_connection_info(
            module, boto3=True)
        aws_connect_kwargs.update(dict(region=region,
                                       endpoint=endpoint,
                                       conn_type='client',
                                       resource='lambda'
                                       ))

        # resource = None
        client = boto3_conn(module, **aws_connect_kwargs)
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg="Can't authorize connection - {0}".format(e))
    except Exception as e:
        module.fail_json(msg="Connection Error - {0}".format(e))
# check if trust_policy is present -- it can be inline JSON or a file path to a JSON file

    function_name = module.params.get('function_name')
    type_in = module.params.get('invocation_type')
    payload = module.params.get('payload')
    environ_override = module.params.get('environment_variables')
    assert_key = module.params.get('assert_key')
    assert_result = module.params.get('assert_result')
    timeout = module.params.get('timeout')

    try:
        with open(payload, 'r') as json_data:
            payload_doc = json.dumps(json.load(json_data))
    except Exception as e:
        module.fail_json(msg=str(e) + ': ' + payload)

    typeList, has_changed = cd_invoke(module, client, function_name, payload_doc,
                                      type_in, assert_key, assert_result, timeout, environ_override)

    module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended


if __name__ == '__main__':
    main()
