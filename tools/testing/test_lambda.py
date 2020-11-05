import os
import sys
import zipfile
import time
import urllib
from shutil import copyfile
import distutils

# import awsconnect
import awsconnect
from awsconnect import awsConnect

from microUtils import loadConfig, yamlRead, account_replace, ansibleSetup, ansible_describe_setup
from microUtils import roleCleaner, role_yaml_clean, writeYaml, loadServicesMap, serviceID

# sudo ansible-playbook -i windows-servers API_Name.yaml -vvvv
dir_path = os.path.dirname(__file__)
real_dir_path = os.path.dirname(os.path.realpath(__file__))
# directory='/path/to/Ansible_Deployer/ansible'

# python Main_DEPLOYER.py -DY dev "test,stage,prod,tpp"  "xx_tablename" ENVRFIG.yaml API_Name true


class LambdaTester():
    incremented = 0

    def __init__(self, parent, directory=None):
        global dir_path
        self.incremented = parent.incremented
        self.directory = directory
        temp = "%s/%s" % (dir_path, directory)
        self.temp = temp
        if not os.path.exists(temp):
            os.makedirs(temp)
        else:
            print(" directory %s already exists... remove or change name." % temp)

    def method_describe(self, target, aconnect):
        client = aconnect.__get_client__('lambda')
        lmda = client.get_function(FunctionName=target)
        cpath = lmda['Code']['Location']
        zipName = "code_%s.zip" % (target)
        urllib.request.urlretrieve(cpath, zipName)
        config = lmda['Configuration']
        vpcs = envars = layers = alias = None
        if 'VpcConfig' in config:
            vpcs = config['VpcConfig']
        if "Layers" in config:
            layers = config["Layers"]
        if 'Environment' in config:
            envars = config['Environment']
        if 'RevisionId' in config:
            alias = config['RevisionId']
        return type('obj', (object,), {
                    'memory': config['MemorySize'],
                    'farn': config['FunctionArn'],
                    'vpcs': vpcs,
                    'envars': envars,
                    'handler': config['Handler'],
                    'lrole': config['Role'],
                    'timeout': config['Timeout'],
                    'runtime': config['Runtime'],
                    'description': config['Description'],
                    'alias': alias,
                    'layers': layers
                    }
                    ), zipName
    # Create files in the ansible/role direcotry after extracting the CEDAR files

    def zip_extract_yaml(self, zipName, indentifier=".cedar."):
        cedarFiles = []
        with zipfile.ZipFile(zipName) as z:
            for filename in z.namelist():
                if ".cedar." in filename:
                    cedarFiles.append(filename)
        if not cedarFiles:
            print(" No testing file found in lambda!!!")
            return False
        testObjs = {}
        # LOOKs inside the zip and extracts the file in question into a python obj
        with zipfile.ZipFile(zipName) as zip:
            for cfile in cedarFiles:
                testObj = {}
                with zip.open(cfile) as f:
                    testObj = yamlRead(None, f)
                    print(testObj)
                    # f.write(z.read('/res/drawable/cfile.png'))
                if testObj:
                    fname = roleCleaner(cfile)
                    testObjs.update({fname: testObj})
        return testObjs

    def collectFiles(self, items):
        folder_files = []
        if isinstance(items, str):
            label, ext = os.path.splitext(items)
            if ext:
                folder_files.append(items)
        elif isinstance(items, list):
            for item in items:
                if isinstance(item, str):
                    label, ext = os.path.splitext(item)
                    if ext:
                        folder_files.append(item)
        return folder_files

    def role_update_paths(self, testObjs, key, value, prefix='{{ role_path }}'):
        if isinstance(value, str):
            label, ext = os.path.splitext(value)
            if ext:
                testObjs[key] = "%s/%s" % (prefix, value)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    label, ext = os.path.splitext(item)
                    if ext:
                        testObjs[key][i] = "%s/%s" % (prefix, item)

    def zip_files_move(self, testObjs, targetRole, roleFolder, zipName):
        roleLabel = role_yaml_clean(targetRole)
        prefix_base = "{{ role_path }}"
        # if roleLabel is in the roleFolder path then this is just a single Main Role

        if roleLabel in roleFolder:
            fileFolder = "%s/files" % (roleFolder)
        else:
            fileFolder = "%s/files/%s" % (roleFolder, targetRole)
            prefix = "%s/files/%s" % (prefix_base, targetRole)
            # prefix = "%s/%s" % (prefix, targetRole)
            if not os.path.exists(fileFolder):
                os.makedirs(fileFolder)
        folder_files = []
        states = ['pre', 'assert', 'post']
        for roleK, rolev in testObjs.items():
            pre = assertin = post = {}
            if 'pre' in rolev:
                pre = rolev['pre']
            if 'assert' in rolev:
                assertin = rolev['assert']
            if 'post' in rolev:
                post = rolev['post']
            run = rolev['run']
            for k, v in pre.items():
                aaf = self.collectFiles(v)
                folder_files = folder_files + aaf
                self.role_update_paths(pre, k, v, prefix)
            for k, v in run.items():
                aaf = self.collectFiles(v)
                folder_files = folder_files + aaf
                self.role_update_paths(run, k, v, prefix)
            for k, v in assertin.items():
                if 'local_path' in k:
                    if '.' in v:
                        assertin['local_path'] = prefix_base
            for k, v in post.items():
                if 'local_path' in k:
                    if '.' in v:
                        post['local_path'] = prefix_base

        for files_in in folder_files:  # Adds folders in root/files folder
            if files_in.startswith("/"):
                files_in = files_in[1:]
            if files_in.endswith("/"):
                files_in = files_in[:-1]
            if "/" not in files_in:
                continue
            folder = files_in.split("/")[0]
            newFolder = "%s/%s" % (fileFolder, folder)
            if not os.path.exists(newFolder):
                os.makedirs(newFolder)
        # folder files are non-modified paths from original .cedar.yaml file

        for ff in folder_files:
            if ff.startswith("/"):
                ff = ff[1:]
            if ff.endswith("/"):
                ff = ff[:-1]
            folder = ff.split("/")[0]
            extractTo = fileFolder
            try:
                base_zip = zipfile.ZipFile(zipName)
                base_zip.extract(ff, extractTo)
                base_zip.close()
            except Exception as e:
                print(e)
                print("[E] %s file not found in zip... check test config.." % ff)
        print("*&*&***&********>>")

        # with zipfile.ZipFile(zipName) as zip:
        #     for ff in folder_files:
        #         with zip.open(ff) as f:

    def define_test(self, sendto, target, aconnect, origin, global_accts, role_alias=None):
        lambdaM, zipName = self.method_describe(target, aconnect)
        testObjs = self.zip_extract_yaml(zipName)
        if not testObjs:
            print(" TEST FILEs NOT FOUND %s:%s" % (role_alias, target))
            return None
        return self.make_ansible(sendto, zipName, testObjs, target,
                                 origin, global_accts, role_alias)

    def make_ansible(self, sendto, zipName, testObjs, targetRole, accountOrigin, accounts, role_alias=None):
        main_role = None
        errors = []
        if role_alias:
            main_role = role_alias
        else:
            main_role = targetRole
        label_main_role = role_yaml_clean(main_role)
        label_sub_role = role_yaml_clean(targetRole)
        taskMain = []
        if self.incremented == 0:
            defaultVar = {label_main_role: {label_sub_role: {}}}
            # get initial setup and add as you need to before writting to file system
            taskMain, rootFolder, targetLabel = ansibleSetup(
                self.temp, main_role, True)
        if role_alias:  # already exists grab latest from file
            taskMain_plus, defaultVar, rootFolder, targetLabel = ansible_describe_setup(
                self.temp, main_role, targetRole)
            taskMain = taskMain + taskMain_plus
            defaultVar.update({label_sub_role: {}})
        if self.incremented == 0:
            taskMain = taskMain[0:2]

        self.zip_files_move(testObjs, targetRole, rootFolder, zipName)
        defaultVar[label_main_role][label_sub_role].update(testObjs)
        #############################################
        #############################################

        acctID = accountOrigin['account']
        m_acctID = acctID.split("_")[0]
        assumeRole = accountOrigin['assume_role']
        NETWORK_MAP = loadServicesMap(accountOrigin['services_map'], 'RDS')
        TOKEN_MAP = loadServicesMap(accountOrigin['services_map'], 'token')
        COGNITO_MAP = loadServicesMap(accountOrigin['services_map'], 'cognito')
        XACT_MAP = loadServicesMap(accountOrigin['services_map'], 'xact')
        BUCKET_MAP = loadServicesMap(accountOrigin['services_map'], 'S3')
        SLACK_MAP = loadServicesMap(accountOrigin['services_map'], 'slack')
        SIGNER_MAP = loadServicesMap(accountOrigin['services_map'], 'signer')
        DOMAIN_MAP = loadServicesMap(accountOrigin['services_map'], 'domains')
        CFRONT_MAP = loadServicesMap(
            accountOrigin['services_map'], 'cloudfront')

        skipping = error_path = None
        acctTitle = "devlpmnt"
        #############################################
        #############################################
        # ####### write YAML to file in tasks  #######
        #############################################
        #############################################
        # BELOW combine service and action to pull the correct Ansible module
        # use for test sequence in order

        test_actions = ['pre', 'run', 'assert', 'post']
        for tk, tv in testObjs.items():
            print(" adding module for %s" % (tk))
            for state in test_actions:
                if state in tv:
                    print("- - -- - ")
                    print(" ==K:%s   V:%s" %
                          (tv[state]['service'], tv[state]['action']))
                    taskMain.append({"import_tasks": "../aws/test_%s_%s.yml" % (tv[state]['service'], tv[state]['action']),
                                     "vars": {"project_local": '{{ project.%s.%s.%s }}' % (label_sub_role, tk, state)}})
                else:
                    print("[W] state:%s NOT found in test file: %s" %
                          (state, tk))

        option = "main"
        mainIn = "%s/%s/%s" % (rootFolder, 'tasks', option)
        writeYaml(taskMain, mainIn)

        #############################################
        # ##########   END WRITE  ####################
        #############################################
        #############################################
        if 'services_map' in accountOrigin:
            mapfile = accountOrigin['services_map']
            serviceMap = loadServicesMap(mapfile, None)
        for akey, account in accounts.items():
            m_account = akey.split("_")[0]
            if akey not in BUCKET_MAP:
                print("[W] account:%s not found in MAP" % (akey))
                continue
            networkObj = NETWORK_MAP[akey]
            bucketObj = BUCKET_MAP[akey]
            cfrontObj = CFRONT_MAP[akey]
            domainObj = DOMAIN_MAP[akey]
            cognitoObj = COGNITO_MAP[akey]
            xactObj = XACT_MAP[akey]
            tokenObj = TOKEN_MAP[akey]
            slackObj = SLACK_MAP[akey]
            signerObj = SIGNER_MAP[akey]
            if akey == acctID:
                acctTitle = account['title']
            eID = serviceID(akey, None, account['all'], serviceMap)
            accDetail = {
                "account_id": akey,
                "error_path": error_path,
                "skipping": skipping,
                "env": acctTitle,
                "role_duration": 3600,
                "region": "us-east-1",
                "eid": eID,
                "roles": [],
                "policies": []
            }
            if assumeRole:
                accDetail.update({"cross_acct_role": account['role']})
            print("*******************")
            print(targetLabel)
            print(defaultVar)
            if defaultVar[targetLabel]:
                defaultVar[targetLabel].update(accDetail)
            else:
                defaultVar = {targetLabel: accDetail}

            option = "main_%s" % account['all']
            mainIn = "%s/%s/%s" % (rootFolder, 'defaults', option)
            writeYaml(defaultVar, mainIn)
            account_replace("%s.yaml" % mainIn, str(m_acctID), str(m_account))

            for key, value in DOMAIN_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(domainObj[key]))

            for key, value in BUCKET_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(bucketObj[key]))

            for key, value in TOKEN_MAP[acctID].items():
                account_replace("%s.yaml" %
                                mainIn, str(value), str(tokenObj[key]))

            for key, value in NETWORK_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(networkObj[key]))

            for key, value in COGNITO_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(cognitoObj[key]))

            for key, value in XACT_MAP[acctID].items():
                account_replace("%s.yaml" %
                                mainIn, str(value), str(xactObj[key]))

            for key, value in SLACK_MAP[acctID].items():
                account_replace("%s.yaml" %
                                mainIn, str(value), str(slackObj[key]))

            for key, value in SIGNER_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(signerObj[key]))

            for key, value in CFRONT_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(cfrontObj[key]))

        print(" .... creating a main.yaml for ansible using dev")
        opt = "main_%s.yaml" % accountOrigin['all']
        src = "%s/%s/%s" % (rootFolder, 'defaults', opt)
        opt2 = "main.yaml"
        dst = "%s/%s/%s" % (rootFolder, 'defaults', opt2)
        copyfile(src, dst)  # copy [dev] as main.yaml
        print(" -------==------===---- COPY START....")
        print(" sending to %s. from %s" % (sendto, rootFolder))
        distutils.dir_util.copy_tree(rootFolder, sendto)
        print(" -------==------===---- FINAL YAML file....")
        ansibleRoot = sendto.split('roles/')[0]
        # all tests if added below would require more loops per ROLE
        targets = ['%s' % main_role]
        rootYML = [{"name": "micro modler for lambda-%s" % main_role,
                    "hosts": "dev",
                    "remote_user": "root",
                    "roles": targets}]
        # ansibleRoot
        writeYaml(rootYML, ansibleRoot, main_role)

        return errors
