#-*-coding:utf-8-*-
import time,logging
import socket, threading, struct
import selectors #基于select模块实现的IO多路复用，建议大家使用
import hashlib
import pdb
import select
import queue
import common
from datetime import datetime
import json
import zlib
import _thread

#logging.basicConfig(level=logging.INFO)
LOGGING_FORMAT = '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s'
DATE_FORMAT = '%y%m%d %H:%M:%S'
logging.basicConfig(
    level = logging.NOTSET,
    format = LOGGING_FORMAT,
    datefmt = DATE_FORMAT,
    filename = 'log/test.log',
    filemode = 'a'
)

# 是否停止线程处理
stop_flag = 0
kError = 0
kOk = 1


class Server:
    def __init__(self, ip, port, conn_mng, connect_ok):
        self._sock = socket.socket()
        self._selector = selectors.DefaultSelector()
        self._recv_queue = {}
        self._send_queue = {}
        self._client_no = 1
        self._ip = ip
        self._port = port
        self._buf = {}
        self._sock_list={}
        self._connect_ok = connect_ok
        self._conn_mng = conn_mng

    def start(self):
        sock = self._sock
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(0)
        sock.bind((self._ip, self._port))
        sock.listen(100)

        selector = self._selector
        self.add_handler(sock.fileno(), self._accept, selectors.EVENT_READ)

        while True:
            events = selector.select(1)
            for key, event in events:
                handler, data = key.data
                if data:
                    handler(**data)
                else:
                    handler()

    def _accept(self):
        while stop_flag != 1:
            try:
                conn, address = self._sock.accept()
            except OSError:
                break
            else:
                conn.setblocking(0)
                no = str(self._client_no)
                self._sock_list[no] = conn
                self._recv_queue[no] = queue.Queue()
                self._send_queue[no] = queue.Queue()
                self._buf[no] = ''
                self.add_handler(self._sock_list[no], self._read, selectors.EVENT_READ, {'conn': conn, 'recv_queue': self._recv_queue[no], 'no':no})
                print("accept: new sock tag=",no)
                self._connect_ok(self._conn_mng, conn, no, self)
                #self.add_handler(self._sock_list[no], self._write, selectors.EVENT_WRITE, {'conn': conn})
                #_thread.start_new_thread(self._write, (self._sock_list[no], self._send_queue[no]))

    def _read(self, conn, recv_queue, no):
        try:
            data = conn.recv(1024)
        except socket.error as e:
            if e.errno == 11:
                pass
            else:
                print("socket error, Error code:", e)
                conn.close()

        if data != '' or self._buf[no] != '':
            self._buf[no] += data.decode()
            if (len(self._buf[no]) < common.headerLen):
                return

            header_data = struct.unpack(common.fmt_str_dict['Header'], self._buf[no][:common.headerLen].encode())#根据unpack的第一参数格式，将数据返回，header_data[0]表示msg_len
            msg_len = int(header_data[0].decode().rstrip('\x00'))#收到的消息可能后面是以\0结尾的，但在python中字符是没有结束符的，所以要删除
            #fix it check_sum不是放在header中的，它是消息最后
            check_sum = header_data[4].decode().rstrip('\x00')
            if msg_len <= len(self._buf[no]):
                data=self._buf[no][:msg_len]
                if check_sum != zlib.crc32(data.encode()) & 0xffffffff:
                    assert("error: check_sum is error")
                self._recv_queue[no].put(self._buf[no][:msg_len])
                print("recv msg package=", self._buf[no][:msg_len])
                logging.info('recv new msg[%s]', self._buf[no][:msg_len])
                self._buf[no] = self._buf[no][msg_len:]



    def _write(self, conn, send_queue):
        while stop_flag != 1:
            if send_queue.empty() == True:
                time.sleep(0.05)

            while not send_queue.empty():
                msg = send_queue.get()
                print("send msg=", msg)
                conn.sendall(msg)


    def get_msg(self, no, msg):
        if self._recv_queue[no].empty():
            return kError;
        msg = self._recv_queue[no].get()
        return kOk


    def send_msg(self, msg_code, msg_no, data):
        msg = common.encode(msg_code, msg_no, data)
        while len(self._sock_list)<1:
            time.sleep(0.05)
        for no in self._sock_list.keys():
            self._send_queue[no].put(msg)
            print("write msg to send_queue;",msg)

    def add_handler(self, fd, handler, event, data=None):
        self._selector.register(fd, event, (handler, data))

    def remove_handler(self, fd):
        self._selector.unregister(fd)


##*****************************下面的函数可以单独放到自己的类中,

conn_mng = {}

def send_test_msg(server):
    msg_no = 1
    for msg_code,userName,pwd,heartBeatInt in common.data_set:
        data = [userName.encode(),pwd.encode(),heartBeatInt.encode()]
        server.send_msg(msg_code, msg_no, data)
        print("send_test_msg, ", msg_no)
        msg_no += 1




class ConnectionMng:
    def __init__(self):
        self._conn_map = {}

    def createConnection(self,tag, conn, server):
        if tag not in self._conn_map:
            new_conn = Connection(tag, conn, server)
            self._conn_map[tag] = new_conn
        return self._conn_map[tag]


    def clearAll(self):
        for key in self._conn_map.keys:
            #sendmsg(kLogout, logout)
            threading.Timer(kLogoutInterval, self._conn_map[key].close)

        self._conn_map.clear()

    def findConn(self,tag):
        if tag not in self._conn_map:
            return kError
        return kOk
    
class Connection:
    def __init__(self,tag, conn, server):
        self._tag = tag
        self._conn = conn
        self._server = server

    def handleMsg(self,msg):
        return kOk 


    def start(self):
        while stop_flag != 1:
            msg = "" 
            if self._server.get_msg(self._tag,msg):
                handleMsg(msg)
            else:
                time.sleep(0.05)

    def close(self):
        self._conn.close()

    
def hanlde_connect_failed(conn, tag):
    pass

def handle_connect_ok(conn_mng, conn, tag, server):
    if (conn_mng.findConn(tag)):
        return
    new_conn = conn_mng.createConnection(tag, conn, server)
    _thread.start_new_thread(new_conn.start,())
    


if __name__ == '__main__':
    common.msg_fmt_init()
    conn_mng = ConnectionMng()
    myServer = Server("192.168.65.128", 9999, conn_mng, handle_connect_ok)
    myServer.start()
    #send_test_msg(myServer)
