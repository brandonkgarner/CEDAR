# (SERVICEs GENERATOR) TOOLS

### microMolder:

**microMolder** will look at the triggers/bindings ["api","s3","cloudwatch", "DynamoDB"] provided in a given configuration to "find" and "define" basic **Ansible** requirements needed to deploy lambdas into other Environments/Accounts.

microMolder [microMolder.py] builds environment definitions needed for Ansible to deploy to target environments. requirements are :

- boto3
- Requires configuration file **[ENVR.yaml]** to match each env credentials.
- params are:
  - **Lambda target** (the name of the lambda to deploy
  - **role-name** used to switch into for each environment
  - **configuration file** , same dir as microMolder.py
  - **Origin Account Number** of source used for creating Ansible definitions
  - **Path of final location** to copy final, Ansible, Role structure
  - **API-TREE** LABEL target to not copy all related API's. (if _null_ , string, is passed Multiple TREE (resources) are defined)
  - **isFullUpdate** copies existing directory to <name>\_old and re-generates **ENTIRE** structure this is much slower!!!
- pass in null for role-name, API-TREE and Path if not needed

Trust for Role must look like (note both api and lambda included):

```javascript
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "apigateway.amazonaws.com",
          "lambda.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

#### Ansible Execution:

- once above ROLE is complete simple ansible call will work like:

```
ansible-playbook -i windows-servers CD-Admin-Users.yml -vvvv
```
