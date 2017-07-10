#-*-coding:utf-8-*-
import time,logging
import socket, threading, struct
import hashlib
import pdb
import select
import queue
import common
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)

class Client(object):
    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(('192.168.65.128', 9999))

    def recv(self):
        buf = ''
        self.socket.setblocking(0)
        while 0xf0f0 != common.stop_flag:
            try:
                rlist, wlist, xlist=select.select([self.socket], [], [], 0.05)
                if [] == rlist:
                    time.sleep(0.05)
                    continue
                while 1:
                    data = ''
                    try:
                        data = bytes.decode(self.socket.recv(1024))
                    except socket.error as e:
                        if e.errno == 11:
                            pass
                        else:
                            print("socket error, Error code:", e)
                            self.socket.close()
                            #stop_flag = 0xf0f0
                            break

                    buf += data
                    if len(buf) < common.headerLen:
                        time.sleep(0.05)
                        continue

                    ret,msg_len,msg_code,msg_no,result,userName,pwd,heartBeatInt = common.decode(buf)
                    if ret == 0:    #0表示消息是完整的
                        print("recv msg: %s,%i,%s,%s,%s"%(msg_code,msg_no,result,userName, pwd))
                        buf = buf[msg_len:]
            except socket.error as msg:
                print("except:%s, socket is closed by peer"%msg)
                break

        self.socket.close()

    def send(self):
        msg_no = 0
        for msg_code,userName,pwd,heartBeatInt in common.data_set:
            print("userName type=",type(userName.encode()))
            data = [userName.encode(),pwd.encode(),heartBeatInt.encode()]
            msg = common.encode(msg_code,msg_no,data)
            print('sendMsg[%s]'% msg)
            msg_no += 1
            self.socket.send(msg)


    def sendJson(self, msg_code, data):
        msg_no = 0
        msg = common.encode(msg_code,msg_no,data)
        self.socket.send(msg)


if __name__ == '__main__':
    myClient = Client()
    myClient.connect()
    myClient.send()

    #测试序列化传输
    s = common.Student('Bob', 20, 88)
    std_data = json.dumps(s, default=lambda obj: obj.__dict__)
    print(std_data)
    data = [std_data.encode()]
    myClient.sendJson('S201',data)
    myClient.recv()


