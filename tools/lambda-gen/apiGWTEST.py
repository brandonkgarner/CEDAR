import boto3


lambda_func_name = 'callmemaybe'
AWS_LAMBDA_API_ID = 'abcd1234'
AWS_REGION = 'us-east-1'

api_client = boto3.client('apigateway', region_name=AWS_REGION)
aws_lambda = boto3.client('lambda', region_name=AWS_REGION)

## create resource
resource_resp = api_client.create_resource(
    restApiId=AWS_LAMBDA_API_ID,
    parentId='foo', # resource id for the Base API path
    pathPart=lambda_func_name
)

## create POST method
put_method_resp = api_client.put_method(
    restApiId=AWS_LAMBDA_API_ID,
    resourceId=resource_resp['id'],
    httpMethod="POST",
    authorizationType="NONE",
    apiKeyRequired=True,

)

lambda_version = aws_lambda.meta.service_model.api_version

uri_data = {
    "aws-region": AWS_REGION,
    "api-version": lambda_version,
    "aws-acct-id": "xyzABC",
    "lambda-function-name": lambda_func_name,
}

uri = "arn:aws:apigateway:{aws-region}:lambda:path/{api-version}/functions/arn:aws:lambda:{aws-region}:{aws-acct-id}:function:{lambda-function-name}/invocations".format(**uri_data)

## create integration
integration_resp = api_client.put_integration(
    restApiId=AWS_LAMBDA_API_ID,
    resourceId=resource_resp['id'],
    httpMethod="POST",
    type="AWS",
    integrationHttpMethod="POST",
    uri=uri,
)

api_client.put_integration_response(
    restApiId=AWS_LAMBDA_API_ID,
    resourceId=resource_resp['id'],
    httpMethod="POST",
    statusCode="200",
    selectionPattern=".*"
)

## create POST method response
api_client.put_method_response(
    restApiId=AWS_LAMBDA_API_ID,
    resourceId=resource_resp['id'],
    httpMethod="POST",
    statusCode="200",
)

uri_data['aws-api-id'] = AWS_LAMBDA_API_ID
source_arn = "arn:aws:execute-api:{aws-region}:{aws-acct-id}:{aws-api-id}/*/POST/{lambda-function-name}".format(**uri_data)

aws_lambda.add_permission(
    FunctionName=lambda_func_name,
    StatementId=uuid.uuid4().hex,
    Action="lambda:InvokeFunction",
    Principal="apigateway.amazonaws.com",
    SourceArn=source_arn
)

# state 'your stage name' was already created via API Gateway GUI
api_client.create_deployment(
    restApiId=AWS_LAMBDA_API_ID,
    stageName="your stage name",
)