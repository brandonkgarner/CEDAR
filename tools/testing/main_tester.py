import os
import sys
import time

# import awsconnect
import awsconnect
from awsconnect import awsConnect

from test_lambda import LambdaTester

from main_ansible_tester import testStart

from microUtils import loadConfig, roleCleaner, serviceID

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# sudo ansible-playbook -i windows-servers API_Name.yaml -vvvv
dir_path = os.path.dirname(__file__)
real_dir_path = os.path.dirname(os.path.realpath(__file__))
# directory='/path/to/Ansible_Deployer/ansible'

# python Main_DEPLOYER.py -DY dev "test,stage,prod,tpp"  "xx_tablename" ENVR.yaml API_Name true


class CEDARTests():
    incremented = 0

    def __init__(self, directory=None):
        pass

    def define_tests(self, type_in, target_roles, origin, global_accts, role_alias):
        region = origin['region']
        accID = origin['account']
        # print("**********")
        # print(origin)
        # print("**********")
        accountRole = global_accts[accID]['role']
        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
        if 'eID' in origin:
            eID = origin['eID']
        if 'services_map' in origin:
            mapfile = origin['services_map']
            eID = serviceID(origin['account'], mapfile, origin['all'])

        print(eID)
        aconnect = awsConnect(accID, eID, accountRole, sts_client, region)
        aconnect.connect()
        errors = []
        results = []
        total = []
        for i, svc_in in enumerate(target_roles):
            # roleString = roleCleaner(role)
            self.incremented = i
            print(" ## OPTIONS TEST ## %s--> [%s]%s, role %s, account originDefinition %s" %
                  (type_in, role_alias, svc_in, accountRole, accID))
            print(
                " !!! [TEST] !! to assume <cross_acct_role> ROLE make sure you set 'assume_role' in 'ENVR.yaml' to True or False as needed")
            test_time = time.time()
            e = self.test_define(type_in, svc_in, aconnect,
                                 origin, global_accts, role_alias)
            if e is None:
                print("[E] %s no tests found" % (svc_in))
                continue
            errors = errors + e
            if not e:
                results.append(svc_in)
            total.append(svc_in)
            print("-[COMPLETED][SVC]-- %s seconds ---" %
                  (time.time() - test_time))
        return errors, results, total

    def test_define(self, type_in, role_name, aconnect, origin, global_accts, role_alias):
        root = os.path.join(dir_path, "../../ansible/roles")
        role = role_name
        if role_alias:
            role = role_alias
        roleString = roleCleaner(role)
        sendto = "%s/%s" % (root, roleString)
        svc = None
        if type_in == "-L":
            svc = LambdaTester(self, "ansible")
            print("LAMBDA TEST here")
        else:
            print("type:%s not defined" % (type_in))
            return []
        # below will create the directories and ansible files within the ansible/role directories for execution
        #
        return svc.define_test(sendto, role_name, aconnect, origin, global_accts, role_alias)


# EXECUTE AGAINST DEFINITIONS
#
#
# PRODUCE RESULTS PASS/FAIL
# python main_tester.py -L stage "CN-DynamoNormalizer" ENVR.yaml
#
#
#
if __name__ == "__main__":
    # global directory
    # directory = os.path.join(dir_path, '../../ansible')
    pwd_a = real_dir_path[1:].split("/")
    pwd_a.pop()
    pwd = "/".join(pwd_a)
    if not pwd.startswith("/"):
        pwd = "/%s" % (pwd)
    found = None
    length = 0
    tot = len(sys.argv) - 1
    SkipDefinition = False
    type_in = str(sys.argv[1]).strip()
    if 'help' in type_in:
        print(" ************************************************************")
        print("      Try using the following PSUEDO after *CONFIG.yaml is correct :")
        print('           python main_tester.py -L stage "CN-DynamoNormalizer" ENVR.yaml')
        print(
            "         -[NOTE]-->  the above will test a lambda in the stage environment")
        print('           python main_tester.py -L stage "CN-DynamoNormalizer,CN-FileTransform" ENVR.yaml')
        print(
            "         -[NOTE]-->  the above will test 2 lambdas split by ',' ")
        print(" ************************************************************")
        exit()

    targetAPI = fullUpdate = target_environments = None
    if tot < 4:
        missing = 6 - tot
        totTypeIn = len(type_in)
        msg = "[E] %s arguments missing... found:%s needs 4+ arguments" % (
            missing, tot)
        if "-" in type_in and totTypeIn < 3:
            example = "... for example: \n   python main_tester.py -L stage 'CN-DynamoNormalizer' ENVR.yaml"
            msg = "%s %s" % (msg, example)
            raise Exception(msg)
    role_alias = None
    target_environments = str(sys.argv[2]).strip().split(",")
    target_roles = str(sys.argv[3]).strip().split(",")
    config = str(sys.argv[4]).strip()  # ENVR.yaml
    if len(target_roles) > 1:
        if tot < 5:  # a general name is required if more than one role is given
            print(
                '[E] please provide a general name "some Alias" for these tests...like:')
            print('           python main_tester.py -L stage "CN-DynamoNormalizer,CN-FileTransform" ENVR.yaml yourAliasHere')
            raise Exception("alias required!!")
        else:
            role_alias = str(sys.argv[5]).strip()

    start_time = time.time()

    # fullpath = "%s/%s" % (real_dir_path, config)
    fullpath = "%s/%s" % (pwd, config)
    for tgt in target_environments:
        orgn, global_accts = loadConfig(fullpath, tgt)
        triggers = orgn['triggers']
        if triggers is None:
            raise ValueError(
                "[E] config file [ %s ] did not load correctly.. PLEASE check / fix and try again" % (fullpath))
    ct = CEDARTests()
    ready = None
    test_time = time.time()
    # print("----START----%s" % tgt)
    # Use first environment defined tests assume its same for all!!
    origin, global_accts = loadConfig(fullpath, target_environments[0])

    errors, results, total = ct.define_tests(
        type_in, target_roles, origin, global_accts, role_alias)
    print(" definition COMPLETE...")
    results = testStart(global_accts, target_environments, target_roles)
    for k, v in results.items():
        for ri, rv in v.items():
            msg = "%s[%s] Account: %s, %s" % (rv['name'], ri, k, rv['value'])
            print(msg)

        # origin, global_accts = loadConfig(fullpath, tgt)
        # e, r, t = ct.testAllRoles(type_in, target_roles, origin, global_accts)
        # t_num = len(t)
        # e_num = len(e)
        # r_num = len(r)
        # print(e)
        # print("          (TOTAL)            (PASSED)                (FAILED)")
        # print("-------------------------------------------------------------------")
        # print("           (%s)                (%s)                    (%s)" %
        #       (t_num, r_num, e_num))
        # print("-[COMPLETED][ENV]-- %s seconds ---" % (time.time() - test_time))

    print("--[FIN]- %s seconds ---" % (time.time() - start_time))
