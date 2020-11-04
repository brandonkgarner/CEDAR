# Ansible (Templates)


This directory reflects the target structure to be used by Jenkins for both Windows and Serverless deployments.  Project(s) will be defined as Role(s) which include all configuration and definitions needed to promote said project successfully to any environment.

Example hello_world.yml is used to demo examples locally using:
```bash
sudo ansible-playbook hello_world.yml -i windows-servers -e "target_env=dev" -v
```
or for final examples:
```bash
sudo ansible-playbook environment.yml -i windows-servers -e "target_env=dev" -v
```

AMAZON PRE-DEFINED DYNAMIC MODULES where created to help alliviate the need to write your own ansible modules. all aws service modules are in the [aws directory]:

* A. CONFIGURATION:  Use configuration as found in the [hello world defaults/main.yml]
```bash
   <yourConfigNameSpace>:
     account_id: "000000000001"
     #account_id: "000000000002"
     env: "dev"
     role_duration: 3600
     region: us-east-1
     #cross_acct_role: Cross_Deployer
     eid: YOUREID445566
    
```
     *note to use roles in different acccounts uncomment _" #cross_acct_role: Cross_Deployer"_*

* B. CREDENTIALS/TARGET REGION: Ensure first line in your role/project/tasks include STS example([hello_world/tasks/main.yml]):
```bash
- name: INITIAL PROJECT SETUP  project VAR
  set_fact:
    project: "{{ <yourConfigNameSpace> }}"
- include: ../aws/sts.yml project={{ project }}
```

* C. Ansible specific modules can be used by including the target need after setting up the configs (the following would dynamically use the configuration to build out VPC , ECS and KMS based services and subservice tasks like security groups etc...):
```bash
- include: ../aws/sts.yml project={{ project }}
- include: ../aws/vpc.yml project={{ project }}
- include: ../aws/ecs.yml project={{ project }}
- include: ../aws/kms.yml project={{ project }}
```
