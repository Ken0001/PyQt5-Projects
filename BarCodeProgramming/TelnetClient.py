import time
import json
import threading

from typing import Tuple, TypeVar, Optional
from telnetlib import Telnet

from CYLog import mylogger

g_mutex = threading.Lock()

class TelnetClient():

    host: str
    port: int
    verbose: bool
    conn: Telnet
    EPILOG: bytes
    ENTER: bytes

    def __init__(self, host='192.168.2.200',
                       port=23,
                       timeout=3,
                       verbose=False):

        self.host = host
        self.port = port
        self.verbose = verbose
        self.conn = self.telnet_connect(host, port, timeout)
        self.EPILOG = b'#'
        self.ENTER = b'\r\n'


    def telnet_connect(self, host: str,
                             port: int,
                             timeout: int = 3) -> Optional[Telnet]:

        try:
            return Telnet(host, port, timeout)            
        except Exception as e:
            mylogger().warning("host: {h}:{p}".format(h=host, p=port) + \
                               ", Connection Fail, timeout")
            mylogger().warning("host: {h}:{p}".format(h=host, p=port) + str(e))
            return None


    def is_connected(self) -> bool: 
        return self.conn is not None


    T = TypeVar('T', None, dict, str)
    def exe_command(self, command: str,
                          encoding: str = 'utf-8') -> Tuple[bool, T]:

        try:
            self.conn.read_very_eager()          
            if self.verbose:
                print('<Sent>')
                print(command)
                print('</Sent>')

            with g_mutex:
                self.conn.write(str(command).encode(encoding) + self.ENTER)
            time.sleep(2)

            out = self.conn.read_very_eager().decode(encoding)

            cmd_result = self.__arrange_result(out)

            if self.verbose:
                print('<RECEIVE>')
                print(cmd_result)
                print('</RECEIVE>')

            return (True, cmd_result)
        except Exception as e:
            return (False, {"reason": "exe_command Error: " + str(e)})


    def sends(self, content: str,
                    timeout: int = 5,
                    verbose: bool = True,
                    expect_string: str = '#',
                    encoding: str = 'utf-8') -> Tuple[bool, str]:

        status=False
        try:
            if expect_string != str(self.EPILOG):
                expect_string=str(expect_string).encode(encoding)
            self.conn.read_very_eager()
            if verbose:
                print('<Sent>')
                print(content)
                print('</Sent>')

            self.conn.write(content.encode() + self.ENTER)

            out = self.conn.read_until(expect_string, timeout).decode(encoding)
            
            if verbose:
                print('<RECEIVE>')
                print(out)
                print('</RECEIVE>')
            if expect_string.decode() in out:
                status=True
        
            return (status, out)
        except Exception as e:
            return (False, {"reason": "sends Error: " + str(e)})


    def close(self) -> None:
        self.conn.close()


    def __arrange_result(self, cmd_out: str) -> TypeVar('T', None, dict, str):
        if (self.port == 23):
            lines = cmd_out.splitlines()[1:-1]
            out = '\n'.join(lines)
            return out.rstrip()
        elif (self.port == 9528):
            while "#:" in cmd_out:
                cmd_out=cmd_out.replace('#:','')
            dict_content = json.loads(cmd_out.replace(':#',''))
            dict_content = eval(str(dict_content))
            return dict_content
        return None

## ========================================

def waitUntilConnect(ip: str = "192.168.2.200",
                     port: int = 23,
                     timeout: int = 180) -> Optional[TelnetClient]:

    start_time = time.time()
    while(time.time() - start_time < timeout):
        dut = TelnetClient(host = ip, port=port)
        time.sleep(2)

        if(dut.is_connected() is True):
            mylogger().info("Dut connection takes time : {t}"\
                            .format(t=(time.time() - start_time)))
            mylogger().info("Successfully connected to %s:%d", ip, port)
            time.sleep(1)
            return dut
        time.sleep(0.3)
    return None

def make_9528_read_cmd(MAC: str,
                       channel: int,
                       attr: str) -> str:

    mylogger().info("Send read command to MAC: %s, attr = %s", MAC, attr)
    data = {"cmd":"read-attr", "attr": attr, "target-id":"0000" + \
            MAC.replace(":","") + ":" + str(channel)}

    script=json.dumps(data)
    return '#:' + script + ':#'

def make_9528_write_cmd(MAC: str,
                        channel: int,
                        attr: str,
                        value: str) -> str:

    mylogger().info("Send write command to MAC: %s, attr = %s", MAC, attr)
    data = {"cmd":"write-attr", "attr": attr, "target-id":"0000" + \
            MAC.replace(":","") + ":" + str(channel), "value": value}

    script=json.dumps(data)
    return '#:' + script + ':#'

if __name__ =='__main__':
    dut = waitUntilConnect(port=23)
    res, out = dut.sends('ls') #make_9528_read_cmd("d0:14:11:bf:ff:ff", 1, "product-id")
    #res, out = dut.exe_command('ls')
    print(res)
    print(out)
