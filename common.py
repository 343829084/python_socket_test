#-*-coding:utf-8-*-
import time,logging
import socket, threading, struct
import hashlib
import pdb
import select
import Queue

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
        ('UTCDate', 16),
        ('Description', 21),
    ),
}

# 需要发送的消息
data_set=(
    ('S101','userName','1234567890','40'),
    ('S101','  XXX  ','newPassword','40'),
)

fmt_str_dict = {}

headerLen = 160

stop_flag = 0xf0f1

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

        # -----以下为应答响应的消息----
        if msg_code == 'A101':  # 登录响应
            result, utcStamp, desc = int(body_data[0].rstrip('\x00')), body_data[1].rstrip('\x00').encode('utf8'), body_data[2].rstrip('\x00').decode('GBK').encode('utf8')
            return (ret, msg_len, msg_code, msg_no, result, utcStamp, desc)

        elif msg_code == 'A201':   # 委托响应
            pass

        #---------下面为请求的消息------------
        elif msg_code == 'S101':    # 登录请求
            userName, pwd, heartBeatInt = body_data[0].rstrip('\x00'), body_data[1].rstrip('\x00'), int(body_data[2].rstrip('\x00'))
            if userName == 'userName':
                result = 1
            else:
                result = 0
            return (ret, msg_len, msg_code, msg_no, result, userName, pwd, heartBeatInt)
        elif msg_code == 'S201':    #委托
            pass
        else:
            print "can't deal with the msg_code[%s]"% msg_code
            ret = 1
            return (ret, msg_len, msg_code)