#-*-coding:utf-8-*-
import time,logging
import socket, threading, struct
import hashlib
import pdb
import select
import Queue
import common
from datetime import datetime

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
                        data = self.socket.recv(300)
                    except socket.error, e:
                        if e.errno == 11:
                            pass
                        else:
                            print "socket error, Error code:", str(e[0]), ", ErrMsg=", e[1]
                            self.socket.close()
                            #stop_flag = 0xf0f0
                            break

                    buf += data
                    if len(buf) < common.headerLen:
                        time.sleep(0.05)
                        continue

                    ret,msg_len,msg_code,msg_no,result,utcStamp,desc = common.decode(buf)
                    if ret == 0:    #0表示消息是完整的
                        curDate = datetime.fromtimestamp(float(utcStamp))
                        print "%s,%i,%s,%s,%s"%(msg_code,msg_no,result,curDate,desc)
                        buf = buf[msg_len:]
            except socket.error as msg:
                print "except:%s, socket is closed by peer"%msg
                break

        self.socket.close()

    def send(self):
        msg_no = 0
        for msg_code,userName,pwd,heartBeatInt in common.data_set:
            data = [userName,pwd,heartBeatInt]
            msg = common.encode(msg_code,msg_no,data)
            print 'sendMsg[%s]'% msg
            msg_no += 1
            self.socket.send(msg)


if __name__ == '__main__':
    myClient = Client()
    myClient.connect()
    myClient.send()
    myClient.recv()


