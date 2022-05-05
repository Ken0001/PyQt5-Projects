import os
import subprocess
import json
import time
import re
import TelnetClient as Tc

from argparse import ArgumentParser
from typing import Optional, Tuple, List, NewType, Union
TelnetCL = NewType('TelnetCL', Tc.TelnetClient)
StrList = List[str]

from DataBase import DummyMACDataBase as MACDB
from CYLog import mylogger


class MainApp(object):

    config: dict
    MAC_db: Optional[MACDB]
    target_SN: str
    default_MAC: str
    stop: bool

    def __init__(self, config_json, MAC_db):
        self.config = config_json
        self.MAC_db = MAC_db
        self.target_SN = self.config['Input']['target_SN']
        self.default_MAC = self.config['Input']['default_MAC'].upper()
        self.target_FW_commit_id = self.config['Input']['FW_commit_id'].lower()
        self.curr_work_dir = os.getcwd()
        self.stop = False

    def run_burn_in(self) -> str:
    # Loop
        if not self.MAC_db.is_valid_MAC(self.default_MAC):
            msg = "default_MAC is invalid !!"
            mylogger().warning(msg)
            return msg

        res, MAC_list = self.load_MAC_list(self.config['Input']['start_MAC'])
        MAC_count = len(MAC_list)
        if (False is res or 0 == MAC_count):
            msg = "load MAC_list failed !!"
            mylogger().warning(msg)
            return msg

    # Start loop
        while ((not self.stop) and MAC_count):
            rev_MAC_id = -1*MAC_count
            time.sleep(1)
            new_MAC = MAC_list[rev_MAC_id]
            mylogger().info("## Target S/N: %s, new MAC: %s, Go !! ",
                            self.target_SN, new_MAC)

    # Wait until connect
            dut = self.wait_until_connect()
            if dut is None:
                continue

    # Check default MAC
            ret, msg = self.check_pcba_default_MAC_in_flash(dut)
            if ret is False:
                continue

    # Check S/N
            ret, msg = self.check_pcba_FW_SN(dut)
            if ret is False:
                continue

    # Check new MAC
            ret, msg = self.is_new_mac_valid(new_MAC)
            if ret is False:
                MAC_count = MAC_count-1
                continue

    # burn in
            ret, msg = self.burn_in_MAC(dut, new_MAC,
                                        self.config['Input']['exe_burn_in_MAC'])
            if ret is False:
                continue

    # Update DB
            self.update_db(new_MAC)

    # countdown
            MAC_count = MAC_count-1

            dut.close()

        return "End Loop"

    def run_force_init(self) -> str:
    # Loop
        if not self.MAC_db.is_valid_MAC(self.default_MAC):
            msg = "default_MAC is invalid !!"
            mylogger().warning(msg)
            return msg

    # Start loop
        while not self.stop:
            time.sleep(1)
            new_MAC = self.default_MAC
            mylogger().info("## Target S/N: %s, new MAC: %s, Go !! ",
                            self.target_SN, new_MAC)

    # Wait until connect
            dut = self.wait_until_connect()
            if dut is None:
                continue

    # if need to burn in new MAC
            ret_check_MAC, msg = self.check_pcba_default_MAC_in_flash(dut)
            if ret_check_MAC is False:
                # burn in new MAC
                ret_burn_in, msg = self.burn_in_MAC(dut, new_MAC, self.config['Input']['exe_burn_in_MAC'])

    # if need to write new SN in json
            ret_check_SN_json, msg = self.check_pcba_SN_json(dut)
            if ret_check_SN_json is False:
                # write new SN in json
                ret_SN_json, msg = self.write_new_SN_in_json(dut, self.target_SN)

    # if need to OTA
            ret_check_SN, msg = self.check_pcba_FW_SN(dut)
            ret_check_commit_id, msg = self.check_pcba_FW_commit_id(dut)
            if ret_check_SN is False or ret_check_commit_id is False:
                # send file
                ret_send_file, msg = self.send_file_to_pcba(dut, 
                self.config['Input']['ota_bin'], "/root/otaConfigFile/STM32G030K8.bin")
                
                if (ret_send_file is False):
                    continue

                ret_OTA, report = self.OTA(dut, self.config['Input']['exe_OTA'])
                if (ret_OTA is False):
                    continue

        return "End Loop"


    def load_MAC_list(self, start_MAC: str) -> Union[Tuple[bool, str], Tuple[bool, StrList]]:
        MAC_list: StrList = []
        try:
            for file in os.listdir(self.curr_work_dir):
                if file.endswith(".mac") is False:
                    continue
                if len(file.split('_')) != 4:
                    continue
                if file.split('_')[1].upper() != start_MAC.replace(":","").upper():
                    continue
                self.target_SN = file.split('_')[0]
                file_path = file
                if os.path.isfile(file_path) is False:
                    continue
                with open(file_path) as f:
                    for line in f.readlines():
                        MAC = line.strip().rstrip()

                        if (False is self.MAC_db.is_valid_MAC(MAC)):
                            msg = "fail with the invalid MAC: {}".format(MAC)
                            mylogger().info(msg)
                            return (False, msg)

                        if (self.MAC_db.select(MAC)):
                            msg = "failed with the same MAC in db: {}".format(MAC)
                            mylogger().info(msg)
                            return (False, MAC)

                        MAC_list.append(MAC)

                ## mkdir -p ./used_MAC && mv file_path ./used_MAC
                #used_folder = "used_MAC"
                #os.makedirs(used_folder, exist_ok=True)
                #mylogger().info("The new directory (%s/) is created!", used_folder)
                #os.rename(file_path, os.path.join(used_folder, file))

            mylogger().debug(MAC_list)
            if len(MAC_list) == 0:
                return (False, "MAC_list count is 0 !!")

            return (True, MAC_list)

        except Exception as e:
            mylogger().critical(str(e))
            raise


    def wait_until_connect(self, ip: str = "192.168.2.200",
                                 port: int = 23,
                                 timeout: int = 180) -> Optional[TelnetCL]:

        mylogger().info("## Wait until connect...")
        return Tc.waitUntilConnect(ip, port, timeout)


    def check_pcba_FW_SN(self, p: TelnetCL,
                               timeout: int = 10) -> Tuple[bool, str]:

        mylogger().info("## checking pcba firmware SN...")
        ret, pcba_MAC = self.get_pcba_MAC(p, timeout)
        if ret is False:
            msg = "timeout when (get_pcba_MAC)"
            mylogger().warning(msg)
            return (False, msg)

        ret, pcba_SN = self.get_pcba_FW_SN(p.host, pcba_MAC, timeout)
        if ret is False:
            msg = "timeout when (get_pcba_FW_SN)"
            mylogger().warning(msg)
            return (False, msg)

        msg: str = 'pass'
        if self.target_SN != pcba_SN:
            msg = "target_SN: {} != pcba_SN: {}".format(self.target_SN, pcba_SN)
            mylogger().info(msg)
            return (False, msg)

        return (True, msg)

    def check_pcba_SN_json(self, p: TelnetCL,
                                 timeout: int = 10) -> Tuple[bool, str]:

        mylogger().info("## checking pcba SN in json...")
        ret, pcba_SN = self.get_pcba_SN_in_json(p, timeout)
        if ret is False:
            msg = "timeout when (get_pcba_SN_in_json)"
            mylogger().warning(msg)
            return (False, msg)

        msg: str = 'pass'
        if self.target_SN != pcba_SN:
            msg = "target_SN: {} != pcba_SN: {}".format(self.target_SN, pcba_SN)
            mylogger().info(msg)
            return (False, msg)

        return (True, msg)

    def check_pcba_FW_commit_id(self, p: TelnetCL,
                                      timeout: int = 10) -> Tuple[bool, str]:

        mylogger().info("## checking pcba Firmware commit id...")
        ret, pcba_MAC = self.get_pcba_MAC(p, timeout)
        if ret is False:
            msg = "timeout when (get_pcba_MAC)"
            mylogger().warning(msg)
            return (False, msg)

        ret, FW_commit_id = self.get_pcba_FW_commit_id(p.host, pcba_MAC, timeout)
        if ret is False:
            msg = "timeout when (get_pcba_FW_commit_id)"
            mylogger().warning(msg)
            return (False, msg)

        msg: str = 'pass'
        if self.target_FW_commit_id != FW_commit_id:
            msg = "target_FW_commit_id: {} != FW_commit_id: {}".format(self.target_FW_commit_id, FW_commit_id)
            mylogger().info(msg)
            return (False, msg)

        return (True, msg)


    def check_pcba_default_MAC_in_flash(self, p: TelnetCL,
                                              timeout: int = 10) -> Tuple[bool, str]:

        mylogger().info("## checking pcba default MAC in flash...")
        ret, pcba_MAC = self.get_pcba_MAC_in_flash(p, timeout)
        if ret is False:
            msg = "timeout when (get_pcba_MAC_in_flash)"
            mylogger().warning(msg)
            return (False, msg)

        msg: str = 'pass'
        if ret and self.default_MAC != pcba_MAC:
            msg = "default_MAC: {} != pcba_MAC: {}".format(self.default_MAC, pcba_MAC)
            mylogger().info(msg)
            return (False, msg)

        return (True, msg)


    def is_new_mac_valid(self, MAC: str) -> Tuple[bool, str]:
        mylogger().info("## is new MAC valid...")
        msg: str = 'pass'
        if not self.MAC_db.is_valid_MAC(MAC):
            mylogger().info("invalid MAC: %s", MAC)
            return (False, msg)

        if self.MAC_db.select(MAC):
            mylogger().info("pass the same MAC in db: %s", MAC)
            return (False, msg)

        return (True, msg)


    def burn_in_MAC(self, p: TelnetCL,
                          MAC: str,
                          execute: bool = True,
                          timeout: int = 10) -> Tuple[bool, str]:

        mylogger().info("## Burn in MAC !!")
        msg: str = 'pass'
        if execute is False:
            return (True, msg)

        start_time = time.time()
        cmd:str = 'flash set HW_NIC1_ADDR ' + MAC.replace(":","")
        while (time.time() - start_time < timeout):
            ret, _ = p.exe_command(cmd)
            if (True is ret):
                break
            time.sleep(2)

        if ret is False:
            msg = "timeout when ({})".format(cmd)
            mylogger().warning(msg)
            return (False, msg)

        ret, pcba_MAC = self.get_pcba_MAC_in_flash(p, timeout)
        if ret is False:
            msg = "timeout when (get_pcba_MAC_in_flash)"
            mylogger().warning(msg)
            return (False, msg)

        if MAC.upper() != pcba_MAC:
            msg = "new_MAC: {} != HW_NIC1_ADDR: {}".format(MAC.upper(), pcba_MAC)
            mylogger().warning(msg)
            return (False, msg)

        return (True, msg)


    def update_db(self, MAC: str) -> None:

        mylogger().info("## Successfully append new MAC: %s in db !!", MAC)
        self.MAC_db.append(MAC)
        self.MAC_db.writeOut()


    def write_new_SN_in_json(self, p: TelnetCL,
                                   new_SN: str,
                                   timeout: int = 10) -> Tuple[bool, str]:

        mylogger().info("## write new SN in json !")
        start_time = time.time()
        msg = "pass"
        content = '{\n  "product-id" : "' + new_SN + '"\n}'

        while (time.time() - start_time < timeout):
            cmd = """echo '""" + content + """' > /etc/device_info.json"""
            ret, out = p.exe_command(cmd)
            if ret is True:
                break

            time.sleep(2)

        if ret is False:
            msg = "timeout when ({})".format(cmd)
            return (False, msg)
        
        ret, out = self.get_pcba_SN_in_json(p, timeout)
        if ret is False:
            msg = "timeout when (get_pcba_SN_in_json)"
            mylogger().warning(msg)
            return (False, msg)

        if out != new_SN:
            msg = "SN_in_json: {} != new_SN: {}".format(out, new_SN)
            mylogger().info(msg)
            return (False, msg)

        return (True, msg)


    def send_file_to_pcba(self, p: TelnetCL,
                                file_path: str,
                                target_path: str,
                                timeout: int = 30) -> Tuple[bool, str]:

        mylogger().info("## Send file (%s) to pcba (%s) !", file_path, target_path)
        ## check file exist
        if os.path.exists(file_path) is False:
            msg = "{} is not exist !!".format(file_path)
            mylogger().warning(msg)
            return (False, msg)
        
        ## run http.server
        http_server = 'python3 -m http.server 7788'
        kill_server = "pkill -f '{}'".format(http_server)
        run_server = "cd '{}' && {} &".format(os.path.dirname(file_path), http_server)
        os.system(run_server)
        time.sleep(1)

        ## ensure http.server is alive
        ret, out = self.is_process_alive(http_server)
        print(out)
        if ret is False:
            msg = out
            mylogger().warning(msg)
            os.system(kill_server)
            return (False, msg)

        ## pcba curl bin file
        start_time = time.time()
        msg = "timeout"
        curl_cmd = "curl http://192.168.2.2:7788/{} -o '{}' --create-dirs"\
                    .format(os.path.basename(file_path), target_path)
        print(curl_cmd)
        while (time.time() - start_time < timeout):
            ret, out = p.exe_command(curl_cmd)
            if ret is False:
                if (out.find('Connection refused') >= 0):
                    msg = 'Connection refused'
                    mylogger().warning("curl failed: %s !", msg)
                    continue
            else:
                msg = "pass"
                os.system(kill_server)
                return (True, msg)
            time.sleep(2)

        os.system(kill_server)
        return (False, msg)


    def OTA(self, p: TelnetCL,
                  execute: bool = True,
                  retry: int = 10) -> dict():

        mylogger().info("## OTA Start !")

        result=True
        report = dict()
        report["message"] = "skip"
        report["success time"] = -1
        # message="skip"
        
        if execute is False:
            return (result, report)

        for i in range(retry):
            line_str = "==========================================="
            mylogger().debug(line_str + "\ntest time = {}\n".format(i) + line_str)
            result=False
            p_device = p

            if isinstance(p_device.conn, Tc.Telnet):
                p_device.sends("sudo rm /root/otaConfigFile/result.json")
                report["message"] = "ready to execute ota..."
                ## do this or ota.log can't be found(relative path)
                p_device.sends("cd ~")
                
                # ret,out=p_device.sends("/root/ota.sh && exit",timeout=15,verbose=True)
                ret, out = p_device.sends("/root/ota.sh", timeout=30, verbose=True)
                p_device.sends("\x03") #seems it doesn't work
                
                mylogger().debug(line_str + "\n")
                ret2, out2 = p_device.sends("cat /root/otaConfigFile/result.json",
                                            timeout=5, verbose=True, expect_string="}")
                
                try:
                    out_json = json.loads(out2.split("json")[-1])
                    mylogger().debug(out_json["result"])
                    mylogger().debug(line_str + "\n")
                    
                    if out_json["result"] == True:
                        mylogger().info("ota success !!")
                        result = True
                        report["success time"] = i+1
                        report["message"] = out
                        p_device.sends("exit")
                        p_device.close()
                        break
                    else:
                        mylogger().warning("ota fail !!")
                        report["message"] = out
                except Exception as e:
                    mylogger().warning("!! probably no result.json..keep trying")
                    mylogger().warning(str(e))
                    report["message"] = str(e)
                    
                p_device.sends("exit")
                p_device.close()
            else:
                # result=False
                report["message"] = "can't connect port 23..."
        return  (result, report)

##==========================================================================================
## Sub function
##==========================================================================================
    def get_pcba_FW_SN(self, ip: str,
                             MAC: str,
                             timeout: int = 10) -> Tuple[bool, str]:

        start_time = time.time()
        pcba_SN = ""
        msg = "timeout"
        while (time.time() - start_time < timeout):
            dut = Tc.waitUntilConnect(ip, port=9528)
            if dut is None:
                return (False, msg)

            ret, out = dut.exe_command(Tc.make_9528_read_cmd(MAC , 1, "product-id"))
            dut.close()
            if ret is True and out['code'] == 0:
                pcba_SN = out['value']
                mylogger().debug("get pcba S/N: %s", pcba_SN)
                return (True, pcba_SN)
            else:
                msg = str(out)
                mylogger().debug("%s", msg)

            time.sleep(2)

        return (False, msg)


    def get_pcba_FW_commit_id(self, ip: str,
                                    MAC: str,
                                    timeout: int = 10) -> Tuple[bool, str]:

        start_time = time.time()
        pcba_commit_id = ""
        msg = "timeout"
        while (time.time() - start_time < timeout):
            dut = Tc.waitUntilConnect(ip, port=9528)
            if (dut is None):
                return (False, msg)

            ret, out = dut.exe_command(Tc.make_9528_read_cmd(MAC , 1, "commit-id"))
            dut.close()
            if ret and out['code'] == 0:
                pcba_commit_id = out['value'].lower()
                mylogger().debug("get pcba commit id: %s", pcba_commit_id)
                return (True, pcba_commit_id)
            else:
                msg = str(out)
                mylogger().debug("%s", msg)

            time.sleep(2)

        return (False, msg)


    def get_pcba_SN_in_json(self, p: TelnetCL,
                                  timeout: int = 10) -> Tuple[bool, str]:

        start_time = time.time()
        pcba_SN = ""
        msg = "timeout"

        while (time.time() - start_time < timeout):
            ret, out = p.exe_command('cat /etc/device_info.json')
            if ret is True:
                dict_content = json.loads(out)
                dict_content = eval(str(dict_content))
                if 'product-id' not in dict_content:
                    continue
                pcba_SN = dict_content['product-id']
                mylogger().debug("get pcba S/N in json: %s", pcba_SN)
                return (True, pcba_SN)

            time.sleep(2)

        return (False, msg)


    def get_pcba_MAC_in_flash(self, p: TelnetCL,
                                    timeout: int = 10) -> Tuple[bool, str]:

        start_time = time.time()
        pcba_MAC = ""

        while (time.time() - start_time < timeout):
            ## to do.....
            ret, out = p.exe_command('''flash get HW_NIC1_ADDR | cut -d '=' -f 2''')
            if ret is True:
                pcba_MAC = ':'.join(re.findall(".{2}", out)).upper()
                mylogger().debug("get pcba MAC in flash: %s", pcba_MAC)
                return (True, pcba_MAC)

            time.sleep(2)
        
        msg = "timeout"
        return (False, msg)

    def get_pcba_MAC(self, p: TelnetCL,
                           timeout: int = 10) -> Tuple[bool, str]:

        start_time = time.time()
        pcba_MAC = ""

        while (time.time() - start_time < timeout):
            ## to do.....
            ret, out = p.exe_command('cat /sys/class/net/br-lan/address')
            if ret and self.MAC_db.is_valid_MAC(out):
                pcba_MAC = out.upper()
                mylogger().debug("get pcba MAC: %s", pcba_MAC)
                return (True, pcba_MAC)

            time.sleep(2)
        
        msg = "timeout"
        return (False, msg)


    def is_process_alive(self, fullCmd: str) -> Union[Tuple[bool, int], Tuple[bool, str]]:

        pid_cmd = "pgrep -f '{}'".format(fullCmd)
        ret, lines = self.do_command(pid_cmd)

        if ret is False:
            msg = lines
            return (False, msg)

        pid = re.findall('[0-9]+', lines)[0]
        if not self.is_float(pid):
            return (False, 'the pid is not a number !')
            
        return (True, int(pid))


    def is_float(self, elem) -> bool:

        try:
            float(elem)
        except ValueError:
            return False
        return True


    def do_command(self, cmd: str) -> Tuple[bool, str]:

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True,
                             stderr=subprocess.PIPE) #, close_fds=True)
        out, err = p.communicate()
        if p.returncode != 0:
            msg = "Non zero exit code:{} executing: {} error: {}"\
                  .format(p.returncode, cmd, err.decode())
            mylogger().warning(msg)
            return (False, msg)

        return (True, out.decode())

if __name__ == '__main__':

# init db
    mylogger().info("## initialize...")
    myDataBase = MACDB()
    myDataBase.show()

# open config file
    with open("config.json") as f:
        config = json.load(f)

# parse args
    parser = ArgumentParser(prog="CYL-PreBarCode",
                            description="CYL-PreBarCode",
                            epilog="enjoy !!!")

    parser.add_argument("-m", help="default MAC", dest="in_MAC", default=config['Input']['default_MAC'])
    parser.add_argument("-i", help="FW commit id", dest="in_commit_id", default=config['Input']['FW_commit_id'])
    parser.add_argument("-s", help="target SN", dest="in_SN", default=config['Input']['target_SN'])

    args = parser.parse_args()

    if args.in_MAC.upper() != config['Input']['default_MAC'].upper():
        config['Input']['default_MAC'] = args.in_MAC.upper()
    if args.in_commit_id.lower() != config['Input']['FW_commit_id'].lower():
        config['Input']['FW_commit_id'] = args.in_commit_id.lower()
    if args.in_SN != config['Input']['target_SN']:
        config['Input']['target_SN'] = args.in_SN

    myApp = MainApp(config, myDataBase)
    #myApp.run_burn_in()
    #os.system('python3 -m http.server 7788 &')
    #os.system('cd ~/Documents/ota/ && python3 -m http.server 7788 &')
    #print(myApp.do_command("ps -h | grep 'python3 -m http.server 7788'"))
    #print(os.path.basename("gg/123.txt"))

    #myApp.load_MAC_list(config['Input']['start_MAC'])

    dut = myApp.wait_until_connect()
    # if (dut is not None):
    #     ret, msg = myApp.burn_in_MAC(dut, "D0:14:11:BF:FF:11")
    #     ret, msg = myApp.write_new_SN_in_json(dut, "12313")
    #     if (ret):
    #         ret, msg = myApp.check_pcba_FW_SN(dut)
    #         print(msg)

    ret, _ = myApp.burn_in_MAC(dut, "d0:14:11:bf:ff:ff")
    print(ret)
    os.system('pause')
