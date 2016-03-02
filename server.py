#-*-coding:utf-8-*-
import time,logging
import socket, threading, struct
import hashlib
import pdb
import select
import Queue
import common
from datetime import datetime
import json

#logging.basicConfig(level=logging.INFO)
LOGGING_FORMAT = '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s'
DATE_FORMAT = '%y%m%d %H:%M:%S'
logging.basicConfig(
    level=logging.NOTSET,
    format=LOGGING_FORMAT,
    datefmt=DATE_FORMAT,
    filename='log/test.log',
    filemode='a'
)

SUCCESS = "login success"
FAILED = "login failed"

# 是否停止线程处理
continue_flag = 1

#sockets from which we except to read
inputs = []
#sockets from which we expect to write
outputs = []
recvSockSet = []

#Outgoing message queues (socket:Queue)
recv_msg_queues = {}
send_msg_queues = {}

class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False
    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration
    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args: # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False


def recvThreadFun():
    print "start recvThread"
    while continue_flag:
        for sock in recvSockSet:
            data = ''
            try:
                data = recv_msg_queues[sock].get_nowait()
            except Queue.Empty:
                continue
            if data == '':
                continue

            # ret,msg_len,msg_code,msg_no,result,userName,pwd,heartBeatInt
            data_set = common.decode(data)
            ret = data_set[0]
            msg_len = data_set[1]
            msg_code = data_set[2]
            msg_no = data_set[3]
            print "recvThread msg_code=%s"%msg_code
            for case in switch(msg_code):
                if case('S101'):     # 登录请求
                    result = data_set[4]
                    userName = data_set[5]
                    pwd = data_set[6]
                    heartBeatInt = data_set[7]
                    if ret == 0:
                        print("RecvMsg[%s,%i,%s,%s,%s,%s]"% (msg_code,msg_no,result,userName,pwd,heartBeatInt))
                        flag = ''
                        if result == 1:
                            flag = SUCCESS
                        else:
                            flag = FAILED
                        utcStamp = time.time()
                        retData = (str(result), str(utcStamp), flag)
                        #send_msg_queues[sock].put(retData)
                        msg = common.encode('A101',msg_no,retData)
                        send_msg_queues[sock].put(msg)
                        break
                        #sock.send(msg)
                    else:
                        print "Error: upack failed"
                if case('S201'):    # 用来测试序列化
                    result = data_set[4]
                    if ret == 0:
                        print(result)
                        rebuild = json.loads(result, object_hook=lambda d: common.Student(d['name'], d['age'], d['score']))
                        print(rebuild)
                if case('S301'): pass


if __name__ == '__main__':
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setblocking(False)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR  , 1)
    server.bind(('192.168.65.128', 9999))
    server.listen(5)

    recvThread = threading.Thread(target=recvThreadFun, args=())
    recvThread.start()

    common.msg_fmt_init()
    #A optional parameter for select is TIMEOUT
    timeout = 0.5

    inputs.append(server)
    buf = {}
    while 0xf0f0 != common.stop_flag:
        rlist , wlist , elist = select.select(inputs, outputs, inputs, timeout)

        for s in rlist :
            if s is server:
                # A "readable" socket is ready to accept a newSocket
                newSocket, client_address = s.accept()
                print "    newSocket from ", client_address
                newSocket.setblocking(0)
                inputs.append(newSocket)
                recvSockSet.append(newSocket)
                recv_msg_queues[newSocket] = Queue.Queue(10)
                send_msg_queues[newSocket] = Queue.Queue(10)
                buf[newSocket] = ''
            else:
                data = ''
                try:
                    data = s.recv(300)
                except socket.error, e:
                    if e.errno == 11:
                        pass
                    else:
                        print "socket error, Error code:", str(e[0]), ", ErrMsg=", e[1]
                        s.close()

                if data != '' or buf[s] != '':
                    buf[s] += data
                    if (len(buf[s]) < common.headerLen):
                        continue

                    header_data = struct.unpack(common.fmt_str_dict['Header'], buf[s][:common.headerLen])
                    msg_len = int(header_data[0].rstrip('\x00'))
                    if msg_len <= len(buf[s]):
                        print "recv msg package"
                        recv_msg_queues[s].put(buf[s][:msg_len])
                        logging.info('recv new msg[%s]', buf[s][:msg_len])
                        buf[s] = buf[s][msg_len:]

                        if s not in outputs:
                            outputs.append(s)
                    # Add output channel for response

        for s in wlist:
            next_msg=''
            try:
                next_msg = send_msg_queues[s].get_nowait()
            except Queue.Empty:
                continue
                #outputs.remove(s)
            #send_msg_queues[s].task_done()
            if next_msg != '':
                print " sending " , next_msg , " to ", s.getpeername()
                s.send(next_msg)


        for s in elist:
            print " exception condition on ", s.getpeername()
            #stop listening for input on the connection
            inputs.remove(s)
            if s in outputs:
                outputs.remove(s)
            s.close()
            #Remove message queue
            #del message_queues[s]

    recvThread.join()





















