#-*-coding:utf-8-*-
import time,logging
import socket, threading, struct
import hashlib
import pdb
import select
import Queue

logging.basicConfig(level=logging.INFO)

SUCCESS = "login success"
FAILED = "login failed"

MsgDefDict = {
    'Header': (
        ('MsgLen', 6),  # 消息头加消息体的长度
        ('MsgCode', 4),    # 消息代码
        ('RecordLen', 6),   # 消息体的长度
        ('MsgNo', 16),      # 消息编号
        ('VerifyData', 128),    # 消息校验和
    ),
    'S101': (   # 登录请求
        ('UserName', 10),
        ('Pwd', 16),
        ('HeartBeatInt', 16),
    ),
    'A101': (   # 登录回应
        ('Result', 1),
        ('HeartBeatInt', 16),
        ('Description', 21),
    ),
}

fmt_str_dict = {}
headerLen = 160

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

stop_flag = 0xf0f1

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

def msg_fmt_init():
    for msg_code in MsgDefDict:
        msg_def = MsgDefDict[msg_code]
        fmt_str = ""
        for field_def in msg_def:
            field_len = field_def[1]
            fmt_str += "%ds"%field_len
        fmt_str_dict[msg_code] = fmt_str


def encode(msg_code, msg_no, data):
    if {} == fmt_str_dict:
        msg_fmt_init()
    # body ----
    fmt_str = fmt_str_dict[msg_code]
    body = struct.pack(fmt_str, *data)

    # header----
    m = hashlib.md5()
    m.update(body)
    md5cks = m.hexdigest().upper()
    fmt_str = fmt_str_dict['Header']
    header_data = (
        str(headerLen+len(body)),
        msg_code,
        str(len(body)),
        str(msg_no),
        md5cks
    )
    header = struct.pack(fmt_str, *header_data)
    return header+body

def decode(data):
    if {} == fmt_str_dict:
        msg_fmt_init()
    ret = 1
    result = 0
    if len(data) < headerLen:
        print "Error: recv data len < headerLen\n"
        ret = 1
    else:
        ret = 0

    header_data = struct.unpack(fmt_str_dict['Header'], data[:headerLen])
    msg_len, msg_code, rec_len, msg_no, verifyData = int(header_data[0].rstrip('\x00')), header_data[1].rstrip('\x00'), int(header_data[2].rstrip('\x00')), int(header_data[3].rstrip('\x00')), header_data[4][:32]

    body_data = struct.unpack(fmt_str_dict[msg_code], data[headerLen:headerLen+rec_len])
    if len(data[headerLen:]) > 0:
        m = hashlib.md5()
        m.update(data[headerLen:headerLen+rec_len])
        if m.hexdigest().upper() != verifyData:
            print "Error: verifyData failed"
            ret = 1
        else:
            ret = 0

        userName, pwd, heartBeatInt = body_data[0].rstrip('\x00'), body_data[1].rstrip('\x00'), int(body_data[2].rstrip('\x00'))

        if userName == 'userName':
            result = 1
        else:
            result = 0

        return (ret, msg_len, msg_code, msg_no, result, userName, pwd, heartBeatInt)



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

            ret,msg_len,msg_code,msg_no,result,userName,pwd,heartBeatInt = decode(data)
            print "recvThread msg_code=%s"%msg_code
            for case in switch(msg_code):
                if case('S101'):     # 登录请求
                    if ret == 0:
                        print("RecvMsg[%s,%i,%s,%s,%s,%s]"% (msg_code,msg_no,result,userName,pwd,heartBeatInt))
                        flag = ''
                        if result == 1:
                            flag = SUCCESS
                        else:
                            flag = FAILED
                        retData = (str(result), str(heartBeatInt), flag)
                        #send_msg_queues[sock].put(retData)
                        msg = encode(msg_code,msg_no,retData)
                        send_msg_queues[sock].put(msg)
                        break
                        #sock.send(msg)
                    else:
                        print "Error: upack failed"
                if case('S201'): pass
                if case('S301'): pass


if __name__ == '__main__':
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setblocking(False)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR  , 1)
    server.bind(('192.168.65.128', 9999))
    server.listen(5)

    recvThread = threading.Thread(target=recvThreadFun, args=())
    recvThread.start()

    msg_fmt_init()

    #recvmutex = threading.Lock()
    #sendmutex = threading.Lock()

    #A optional parameter for select is TIMEOUT
    timeout = 0.5

    inputs.append(server)
    buf = {}
    while 0xf0f0 != stop_flag:
        #print "waiting for next event"
        rlist , wlist , elist = select.select(inputs, outputs, inputs, timeout)

        # When timeout reached , select return three empty lists
        #if [] == rlist :
            #time.sleep(timeout)
            #continue

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
                    if (len(buf[s]) < headerLen):
                        continue

                    header_data = struct.unpack(fmt_str_dict['Header'], buf[s][:headerLen])
                    msg_len = int(header_data[0].rstrip('\x00'))
                    if msg_len <= len(buf[s]):
                        print "recv msg package"
                        recv_msg_queues[s].put(buf[s][:msg_len])
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





















