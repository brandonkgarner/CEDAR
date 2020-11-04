# Tools (LIBS)

#### There are multiple tools here to help with deployment

## xx-gtwDescribe (runs in each account w/ cloudwatch)

#### Used to describe gateways and then stores the results on S3

## xx-gtwRestore (runs in each account w/ cloudwatch)

#### Used to restore from files built by xx-gtwDescribe

## Lambda-gen

#### Used to generate complete Ansible deployment role for any target service using config files from ENVR.yaml AND RESTRICTED.yaml.

- GENERATION: microMolder: -L for lambda -CF for cloudfront -G for ApiGateway -S3 for buckets -DY for dynamo -SQ for SQS

```bash
python microMolder.py -L xx-LambdaName true ENVR.yaml '/path/to/CR-AWriteCheck' API_Name true
```

- DEPLOYMENT: for generation accross all [CSV AWS accounts] AFTER microMOlder you can use MMAnsibleDeployAll:

```bash
python MMAnsibleDeployAll.py "xx-stage,xx-test" Quickboks_temp ENVR.yaml
```

- NETWORK: buildng multiple access capabilities for both private and public subnets includes: \*_ NAT steps:
  /_: 1. Create a new subnet, e.g. 'public-subnet' 2. Create a route table, e.g. 'public-route-table' 3. Route all outbound 0.0.0.0/0 traffic in 'public-route-table' to your igw 4. Create a route table association between 'public-subnet' and 'public-route-table' 5. Create a NAT Gateway in 'public-subnet' 6. Route all outbound 0.0.0.0/0 traffic in your main route table to your nat
  \*/

## s3-bucket-transfer

#### Simple S3 transfer script that uses awsconnect.py to STS into each account.

## simpleDynamoPut

#### Simple Dynamodb transfer script that uses awsconnect.py to STS into each account.
