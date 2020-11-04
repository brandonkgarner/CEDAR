#!/usr/bin/python
# (c) 2016, Pierre Jodouin <pjodouin@virtualcomputing.solutions>
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

import sys
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
module: cr_lambda_event
short_description: Creates, updates or deletes AWS Lambda function event mappings.
description:
    - This module allows the management of AWS Lambda function event source mappings such as S3 bucket
      events, DynamoDB and Kinesis streaming events via the Ansible framework.
      It is idempotent and supports "Check" mode.  Use module M(lambda) to manage the lambda
      function itself and M(lambda_alias) to manage function aliases.
version_added: "2.1"
author: Pierre Jodouin (@pjodouin)
options:
  lambda_function_arn:
    description:
      - The name or ARN of the lambda function.
    required: true
    aliases: ['function_name', 'function_arn']
  state:
    description:
      - Describes the desired state and defaults to "present".
    required: true
    default: "present"
    choices: ["present", "absent"]
  alias:
    description:
      - Name of the function alias. Mutually exclusive with C(version).
    required: true
  version:
    description:
      -  Version of the Lambda function. Mutually exclusive with C(alias).
    required: false
  event_source:
    description:
      -  Source of the event that triggers the lambda function.
    required: true
    choices: ['s3', 'Kinesis', 'DynamoDB', 'SNS']
  source_params:
    description:
      -  Sub-parameters required for event source.
      -  I(== S3 event source ==)
      -  C(id) Unique ID for this source event.
      -  C(bucket) Name of source bucket.
      -  C(prefix) Bucket prefix (e.g. images/)
      -  C(suffix) Bucket suffix (e.g. log)
      -  C(events) List of events (e.g. ['s3:ObjectCreated:Put'])
      -  I(== stream event source ==)
      -  C(source_arn) The Amazon Resource Name (ARN) of the Kinesis or DynamoDB stream that is the event source.
      -  C(enabled) Indicates whether AWS Lambda should begin polling the event source. Default is True.
      -  C(batch_size) The largest number of records that AWS Lambda will retrieve from your event source at the
         time of invoking your function. Default is 100.
      -  C(starting_position) The position in the stream where AWS Lambda should start reading.
         Choices are TRIM_HORIZON or LATEST.
      -  I(== SNS event source ==)
      -  C(id) Unique ID for this source event.
      -  C(topic_arn) The ARN of the topic to which you want to subscribe the lambda function.
    required: true
requirements:
    - boto3
extends_documentation_fragment:
    - aws

'''

EXAMPLES = '''
---
# Simple example that creates a lambda event notification for an S3 bucket
- hosts: localhost
  gather_facts: no
  vars:
    state: present
  tasks:
  - name: S3 event mapping
    lambda_event:
      state: "{{ state | default('present') }}"
      event_source: s3
      function_name: ingestData
      alias: Dev
      source_params:
        id: lambda-s3-myBucket-create-data-log
        bucket: buzz-scanner
        prefix: twitter
        suffix: log
        events:
        - s3:ObjectCreated:Put

# Example that creates a lambda event notification for a DynamoDB stream
- hosts: localhost
  gather_facts: no
  vars:
    state: present
  tasks:
  - name: DynamoDB stream event mapping
    lambda_event:
      state: "{{ state | default('present') }}"
      event_source: stream
      function_name: "{{ function_name }}"
      alias: Dev
      source_params:
        source_arn: arn:aws:dynamodb:us-east-1:123456789012:table/tableName/stream/2016-03-19T19:51:37.457
        enabled: True
        batch_size: 100
        starting_position: TRIM_HORIZON

  - name: show source event
    debug: var=lambda_stream_events

# example of SNS topic
  - name: SNS event mapping
    lambda_event:
      state: "{{ state | default('present') }}"
      event_source: sns
      function_name: SaveMessage
      alias: Prod
      source_params:
        id: lambda-sns-topic-notify
        topic_arn: arn:aws:sns:us-east-1:123456789012:sns-some-topic

  - name: show SNS event mapping
    debug: var=lambda_sns_event

'''

RETURN = '''
---
lambda_s3_events:
    description: list of dictionaries returned by the API describing S3 event mappings
    returned: success
    type: list
lambda_stream_events:
    description: list of dictionaries returned by the API describing stream event mappings
    returned: success
    type: list
lambda_sns_event:
    description: dictionary returned by the API describing SNS event mapping
    returned: success
    type: dict

'''

# ---------------------------------------------------------------------------------------------------
#
#   Helper Functions & classes
#
# ---------------------------------------------------------------------------------------------------


class AWSConnection:
    """
    Create the connection object and client objects as required.
    """

    def __init__(self, ansible_obj, resources, boto3=True):

        try:
            self.region, self.endpoint, aws_connect_kwargs = get_aws_connection_info(ansible_obj, boto3=boto3)

            self.resource_client = dict()
            if not resources:
                resources = ['lambda']

            resources.append('iam')

            for resource in resources:
                aws_connect_kwargs.update(dict(region=self.region,
                                               endpoint=self.endpoint,
                                               conn_type='client',
                                               resource=resource
                                               ))
                self.resource_client[resource] = boto3_conn(ansible_obj, **aws_connect_kwargs)

            # if region is not provided, then get default profile/session region
            if not self.region:
                self.region = self.resource_client['lambda'].meta.region_name

        except (ClientError, ParamValidationError, MissingParametersError) as e:
            ansible_obj.fail_json(msg="Unable to connect, authorize or access resource: {0}".format(e))

        # set account ID
        try:
            self.account_id = self.resource_client['iam'].get_user()['User']['Arn'].split(':')[4]
        except (ClientError, ValueError, KeyError, IndexError):
            self.account_id = ''

    def client(self, resource='lambda'):
        return self.resource_client[resource]


def pc(key):
    """
    Changes python key into Pascale case equivalent. For example, 'this_function_name' becomes 'ThisFunctionName'.

    :param key:
    :return:
    """

    return "".join([token.capitalize() for token in key.split('_')])


def ordered_obj(obj):
    """
    Order object for comparison purposes

    :param obj:
    :return:
    """

    if isinstance(obj, dict):
        return sorted((k, ordered_obj(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return sorted(ordered_obj(x) for x in obj)
    else:
        return obj


def set_api_sub_params(params):
    """
    Sets module sub-parameters to those expected by the boto3 API.

    :param module_params:
    :return:
    """

    api_params = dict()

    for param in params.keys():
        param_value = params.get(param, None)
        if param_value:
            api_params[pc(param)] = param_value

    return api_params


def validate_params(module, aws):
    """
    Performs basic parameter validation.

    :param module:
    :param aws:
    :return:
    """

    function_name = module.params['lambda_function_arn']

    # validate function name
    if not re.search('^[\w\-:]+$', function_name):
        module.fail_json(
                msg='Function name {0} is invalid. Names must contain only alphanumeric characters and hyphens.'.format(function_name)
        )
    if ':' in function_name:
        if len(function_name) > 140:
            module.fail_json(msg='Function ARN "{0}" exceeds 140 character limit'.format(function_name))
    else:
        if len(function_name) > 64:
            module.fail_json(msg='Function name "{0}" exceeds 64 character limit'.format(function_name))

    # check if 'function_name' needs to be expanded in full ARN format
    if not module.params['lambda_function_arn'].startswith('arn:aws:lambda:'):
        function_name = module.params['lambda_function_arn']
        module.params['lambda_function_arn'] = 'arn:aws:lambda:{0}:{1}:function:{2}'.format(aws.region, aws.account_id, function_name)

    qualifier = get_qualifier(module)
    if qualifier:
        function_arn = module.params['lambda_function_arn']
        module.params['lambda_function_arn'] = '{0}:{1}'.format(function_arn, qualifier)

    return


def get_qualifier(module):
    """
    Returns the function qualifier as a version or alias or None.

    :param module:
    :return:
    """

    qualifier = None
    if module.params['version'] > 0:
        qualifier = str(module.params['version'])
    elif module.params['alias']:
        qualifier = str(module.params['alias'])

    return qualifier


def assert_policy_state(module, aws, policy, present=False):
    """
    Asserts the desired policy statement is present/absent and adds/removes it accordingly.

    :param module:
    :param aws:
    :param policy:
    :param present:
    :return:
    """

    changed = False
    currently_present = get_policy_state(module, aws, policy['statement_id'])

    if present:
        if not currently_present:
            changed = add_policy_permission(module, aws, policy)
    else:
        if currently_present:
            changed = remove_policy_permission(module, aws, policy['statement_id'])

    return changed


def get_policy_state(module, aws, sid):
    """
    Checks that policy exists and if so, that statement ID is present or absent.

    :param module:
    :param aws:
    :param sid:
    :return:
    """

    client = aws.client('lambda')
    policy = dict()
    present = False

    # set API parameters
    api_params = dict(FunctionName=module.params['lambda_function_arn'])
    qualifier = get_qualifier(module)
    if qualifier:
        api_params.update(Qualifier=qualifier)

    # check if function policy exists
    try:
        # get_policy returns a JSON string so must convert to dict before reassigning to its key
        policy_results = client.get_policy(**api_params)
        policy = json.loads(policy_results.get('Policy', '{}'))

    except (ClientError, ParamValidationError, MissingParametersError) as e:
        if not e.response['Error']['Code'] == 'ResourceNotFoundException':
            module.fail_json(msg='Error retrieving function policy: {0}'.format(e))

    if 'Statement' in policy:
        # now that we have the policy, check if required permission statement is present
        for statement in policy['Statement']:
            if statement['Sid'] == sid:
                present = True
                break

    return present


def add_policy_permission(module, aws, policy_statement):
    """
    Adds a permission statement to the policy.

    :param module:
    :param aws:
    :param policy_statement:
    :return:
    """

    client = aws.client('lambda')
    changed = False

    # set API parameters
    api_params = dict(FunctionName=module.params['lambda_function_arn'])
    api_params.update(set_api_sub_params(policy_statement))
    qualifier = get_qualifier(module)
    if qualifier:
        api_params.update(Qualifier=qualifier)

    try:
        if not module.check_mode:
            client.add_permission(**api_params)
        changed = True
    except (ClientError, ParamValidationError, MissingParametersError) as e:
        module.fail_json(msg='Error adding permission to policy: {0}'.format(e))

    return changed


def remove_policy_permission(module, aws, statement_id):
    """
    Removed a permission statement from the policy.

    :param module:
    :param aws:
    :param statement_id:
    :return:
    """

    client = aws.client('lambda')
    changed = False

    # set API parameters
    api_params = dict(FunctionName=module.params['lambda_function_arn'])
    api_params.update(StatementId=statement_id)
    qualifier = get_qualifier(module)
    if qualifier:
        api_params.update(Qualifier=qualifier)

    try:
        if not module.check_mode:
            client.remove_permission(**api_params)
        changed = True
    except (ClientError, ParamValidationError, MissingParametersError) as e:
        module.fail_json(msg='Error removing permission from policy: {0}'.format(e))

    return changed


# ---------------------------------------------------------------------------------------------------
#
#   Lambda Event Handlers
#
#   This section defines a lambda_event_X function where X is an AWS service capable of initiating
#   the execution of a Lambda function.
#
# ---------------------------------------------------------------------------------------------------


def lambda_event_stream(module, aws):
    """
    Adds, updates or deletes lambda stream (DynamoDb, Kinesis) envent notifications.
    :param module:
    :param aws:
    :return:
    """

    client = aws.client('lambda')
    facts = dict()
    changed = False
    current_state = 'absent'
    state = module.params['state']

    api_params = dict(FunctionName=module.params['lambda_function_arn'])

    # check if required sub-parameters are present and valid
    source_params = module.params['source_params']

    source_arn = source_params.get('source_arn')
    if source_arn:
        api_params.update(EventSourceArn=source_arn)
    else:
        module.fail_json(msg="Source parameter 'source_arn' is required for stream event notification.")

    # check if optional sub-parameters are valid, if present
    batch_size = source_params.get('batch_size')
    if batch_size:
        try:
            source_params['batch_size'] = int(batch_size)
        except ValueError:
            module.fail_json(msg="Source parameter 'batch_size' must be an integer, found: {0}".format(source_params['batch_size']))

    # optional boolean value needs special treatment as not present does not imply False
    source_param_enabled = None
    if source_params.get('enabled') is not None:
        source_param_enabled = module.boolean(source_params['enabled'])

    # check if event mapping exist
    try:
        facts = client.list_event_source_mappings(**api_params)['EventSourceMappings']
        if facts:
            current_state = 'present'
    except ClientError as e:
        module.fail_json(msg='Error retrieving stream event notification configuration: {0}'.format(e))

    if state == 'present':
        if current_state == 'absent':

            starting_position = source_params.get('starting_position')
            if starting_position:
                api_params.update(StartingPosition=starting_position)
            else:
                module.fail_json(msg="Source parameter 'starting_position' is required for stream event notification.")

            enabled = source_params.get('enabled')
            if source_arn:
                api_params.update(Enabled=enabled)
            batch_size = source_params.get('batch_size')
            if batch_size:
                api_params.update(BatchSize=batch_size)

            try:
                if not module.check_mode:
                    facts = client.create_event_source_mapping(**api_params)
                changed = True
            except (ClientError, ParamValidationError, MissingParametersError) as e:
                module.fail_json(msg='Error creating stream source event mapping: {0}'.format(e))

        else:
            # current_state is 'present'
            api_params = dict(FunctionName=module.params['lambda_function_arn'])
            current_mapping = facts[0]
            api_params.update(UUID=current_mapping['UUID'])
            mapping_changed = False

            # check if anything changed
            if source_params.get('batch_size') and source_params['batch_size'] != current_mapping['BatchSize']:
                api_params.update(BatchSize=source_params['batch_size'])
                mapping_changed = True

            if source_param_enabled is not None:
                if source_param_enabled:
                    if current_mapping['State'] not in ('Enabled', 'Enabling'):
                        api_params.update(Enabled=True)
                        mapping_changed = True
                else:
                    if current_mapping['State'] not in ('Disabled', 'Disabling'):
                        api_params.update(Enabled=False)
                        mapping_changed = True

            if mapping_changed:
                try:
                    if not module.check_mode:
                        facts = client.update_event_source_mapping(**api_params)
                    changed = True
                except (ClientError, ParamValidationError, MissingParametersError) as e:
                    module.fail_json(msg='Error updating stream source event mapping: {0}'.format(e))

    else:
        if current_state == 'present':
            # remove the stream event mapping
            api_params = dict(UUID=facts[0]['UUID'])

            try:
                if not module.check_mode:
                    facts = client.delete_event_source_mapping(**api_params)
                changed = True
            except (ClientError, ParamValidationError, MissingParametersError) as e:
                module.fail_json(msg='Error removing stream source event mapping: {0}'.format(e))

    return dict(changed=changed, ansible_facts=dict(lambda_stream_events=facts))


def lambda_event_s3(module, aws):
    """
    Adds, updates or deletes lambda s3 event notifications.

    :param module: Ansible module reference
    :param aws:
    :return dict:
    """

    client = aws.client('s3')
    api_params = dict()
    changed = False
    current_state = 'absent'
    state = module.params['state']

    # check if required sub-parameters are present
    source_params = module.params['source_params']
    if not source_params.get('id'):
        module.fail_json(msg="Source parameter 'id' is required for S3 event notification.")

    if source_params.get('bucket'):
        api_params = dict(Bucket=source_params['bucket'])
    else:
        module.fail_json(msg="Source parameter 'bucket' is required for S3 event notification.")

    # check if event notifications exist
    try:
        facts = client.get_bucket_notification_configuration(**api_params)
        facts.pop('ResponseMetadata')
    except ClientError as e:
        module.fail_json(msg='Error retrieving s3 event notification configuration: {0}'.format(e))

    current_lambda_configs = list()
    matching_id_config = dict()
    if 'LambdaFunctionConfigurations' in facts:
        current_lambda_configs = facts.pop('LambdaFunctionConfigurations')

        for config in current_lambda_configs:
            if config['Id'] == source_params['id']:
                matching_id_config = config
                current_lambda_configs.remove(config)
                current_state = 'present'
                break

    if state == 'present':
        # build configurations
        new_configuration = dict(Id=source_params.get('id'))
        new_configuration.update(LambdaFunctionArn=module.params['lambda_function_arn'])

        filter_rules = []
        if source_params.get('prefix'):
            filter_rules.append(dict(Name='Prefix', Value=str(source_params.get('prefix'))))
        if source_params.get('suffix'):
            filter_rules.append(dict(Name='Suffix', Value=str(source_params.get('suffix'))))
        if filter_rules:
            new_configuration.update(Filter=dict(Key=dict(FilterRules=filter_rules)))
        if source_params.get('events'):
            new_configuration.update(Events=source_params['events'])

        if current_state == 'present':

            # check if source event configuration has changed
            if ordered_obj(matching_id_config) == ordered_obj(new_configuration):
                current_lambda_configs.append(matching_id_config)
            else:
                # update s3 event notification for lambda
                current_lambda_configs.append(new_configuration)
                facts.update(LambdaFunctionConfigurations=current_lambda_configs)
                api_params = dict(NotificationConfiguration=facts, Bucket=source_params['bucket'])

                try:
                    if not module.check_mode:
                        client.put_bucket_notification_configuration(**api_params)
                    changed = True
                except (ClientError, ParamValidationError, MissingParametersError) as e:
                    module.fail_json(msg='Error updating s3 event notification for lambda: {0}'.format(e))

        else:
            # add policy permission before creating the event notification
            policy = dict(
                statement_id=source_params['id'],
                action='lambda:InvokeFunction',
                principal='s3.amazonaws.com',
                source_arn='arn:aws:s3:::{0}'.format(source_params['bucket']),
                source_account=aws.account_id,
            )
            assert_policy_state(module, aws, policy, present=True)

            # create s3 event notification for lambda
            current_lambda_configs.append(new_configuration)
            facts.update(LambdaFunctionConfigurations=current_lambda_configs)
            api_params = dict(NotificationConfiguration=facts, Bucket=source_params['bucket'])

            try:
                if not module.check_mode:
                    client.put_bucket_notification_configuration(**api_params)
                changed = True
            except (ClientError, ParamValidationError, MissingParametersError) as e:
                module.fail_json(msg='Error creating s3 event notification for lambda: {0}'.format(e))

    else:
        # state = 'absent'
        if current_state == 'present':

            # delete the lambda event notifications
            if current_lambda_configs:
                facts.update(LambdaFunctionConfigurations=current_lambda_configs)

            api_params.update(NotificationConfiguration=facts)

            try:
                if not module.check_mode:
                    client.put_bucket_notification_configuration(**api_params)
                changed = True
            except (ClientError, ParamValidationError, MissingParametersError) as e:
                module.fail_json(msg='Error removing s3 source event configuration: {0}'.format(e))

            policy = dict(
                statement_id=source_params['id'],
            )
            assert_policy_state(module, aws, policy, present=False)

    return dict(changed=changed, ansible_facts=dict(lambda_s3_events=current_lambda_configs))


def lambda_event_sns(module, aws):
    """
    Adds, updates or deletes lambda sns event notifications.

    :param module: Ansible module reference
    :param aws:
    :return dict:
    """

    client = aws.client('sns')
    api_params = dict()
    changed = False
    current_state = 'absent'
    state = module.params['state']

    # check if required sub-parameters are present
    source_params = module.params['source_params']
    if not source_params.get('id'):
        module.fail_json(msg="Source parameter 'id' is required for SNS event.")

    if source_params.get('topic_arn'):
        api_params = dict(TopicArn=source_params['topic_arn'])
    else:
        module.fail_json(msg="Source parameter 'topic_arn' is required for SNS event.")

    # check if SNS subscription exists
    current_subscription = dict()
    endpoint = module.params['lambda_function_arn']
    try:
        while not current_subscription:
            facts = client.list_subscriptions_by_topic(**api_params)
            for subscription in facts.get('Subscriptions', []):
                if subscription['Endpoint'] == endpoint:
                    current_subscription = subscription
                    current_state = 'present'
                    break

            # if there are more than 100 subscriptions, NextToken will be present so if
            # subscription is not found yet, get next block starting at NextToken
            if 'NextToken' in facts and not current_subscription:
                api_params.update(NextToken=facts['NextToken'])
            else:
                break

    except (ClientError, ParamValidationError, MissingParametersError) as e:
        module.fail_json(msg='Error retrieving SNS subscriptions: {0}'.format(e))

    if state == 'present':
        if current_state == 'present':
            # subscription cannot be updated so nothing to do here
            pass
        else:
            # add policy permission before creating the subscription
            policy = dict(
                statement_id=source_params['id'],
                action='lambda:InvokeFunction',
                principal='sns.amazonaws.com',
                source_arn=source_params['topic_arn'],
            )
            assert_policy_state(module, aws, policy, present=True)

            # create subscription
            api_params = dict(
                TopicArn=source_params['topic_arn'],
                Endpoint=endpoint,
                Protocol='lambda'
            )
            try:
                if not module.check_mode:
                    current_subscription = client.subscribe(**api_params)
                changed = True
            except (ClientError, ParamValidationError, MissingParametersError) as e:
                module.fail_json(msg='Error creating SNS event mapping for lambda: {0}'.format(e))

    else:
        if current_state == 'present':
            # remove subscription
            api_params = dict(SubscriptionArn=current_subscription['SubscriptionArn'])
            try:
                if not module.check_mode:
                    client.unsubscribe(**api_params)
                current_subscription = dict()
                changed = True
            except (ClientError, ParamValidationError, MissingParametersError) as e:
                module.fail_json(msg='Error removing SNS event mapping for lambda: {0}'.format(e))

            # remove policy associated with this event mapping 
            policy = dict(
                statement_id=source_params['id'],
            )
            assert_policy_state(module, aws, policy, present=False)

    return dict(changed=changed, ansible_facts=dict(lambda_sns_event=current_subscription))


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
    source_choices = [function.split('_')[-1] for function in dir(this_module) if function.startswith('lambda_event')]

    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        state=dict(required=False, default='present', choices=['present', 'absent']),
        lambda_function_arn=dict(required=True, default=None, aliases=['function_name', 'function_arn']),
        event_source=dict(required=True, default=None, choices=source_choices),
        source_params=dict(type='dict', required=True, default=None),
        alias=dict(required=False, default=None),
        version=dict(type='int', required=False, default=0),
        )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=[['alias', 'version']],
        required_together=[]
    )

    # validate dependencies
    if not HAS_BOTO3:
        module.fail_json(msg='Both boto3 & boto are required for this module.')

    aws = AWSConnection(module, ['lambda', 's3', 'sns'])

    validate_params(module, aws)

    this_module_function = getattr(this_module, 'lambda_event_{0}'.format(module.params['event_source'].lower()))

    results = this_module_function(module, aws)

    module.exit_json(**results)


# ansible import module(s) kept at ~eof as recommended
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()