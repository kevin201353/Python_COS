#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 ShenCloud Inc.

"""loginproess module"""

import logging
import httplib

log = logging.getLogger(__name__)

UPGRADE_INFO = '/var/upgrade.info'

VM_INFO = '''    <vm_info>
        <vm_id>%s</vm_id>
        <vm_name>%s</vm_name>
        <vm_user>%s</vm_user>
    </vm_info>
'''

VMS_INFO_MSG = '''<vms_info>
%s</vms_info>'''

QUERY_VM_MSG = '''<query_vm>
    <vm_id>%s</vm_id>
</query_vm>'''

err_code = {
    'OK': '成功',
    'SERVER_RET_ERR': '该虚拟机用户未上线，无法获取连接权限！',
    'CONN_SERVER_FAILED': '连接升级服务器失败, 请检查服务器是否开启, \n地址是否正确，网络是否正常！',
    'NOT_CONF_SERVER': '连接需通过升级服务器，请配置升级服务器地址。',
}

def get_server(server_type):
    upgrade_str = ''
    server_ip, server_port = None, None
    with open(UPGRADE_INFO, 'r') as upgrade_info_name:
        upgrade_info = upgrade_info_name.readlines()
        i = 0
        for info in upgrade_info:
            upgrade_str = info.strip()
            if upgrade_str == server_type:
                upgrade_str = upgrade_info[i+1].strip()
                break
            i += 1
        else:
            return None, None
    strr = upgrade_str.strip()[len('http://'):]
    server_ip, server_port = strr.split(':')

    return server_ip, server_port


def send_user_vms(vms_list=[]):
    if not vms_list:
        return

    global VM_INFO, VMS_INFO_MSG
    vm_info = vms_info_msg = ''
    for vm in vms_list:
        vm_info += VM_INFO % (vm['id'], vm['name'], vm['user'])

    vms_info_msg = VMS_INFO_MSG % vm_info
    send_msg_to_server(vms_info_msg, '<tcm server>')


def send_msg_to_server(send_msg, server_type):
    server_ip, server_port = get_server(server_type)
    ret = ''

    if server_ip and server_port:
        server = '%s:%s' % (server_ip, server_port)
        try:
            http_conn = httplib.HTTPConnection(server_ip, server_port)
            http_conn.request('POST', '/client_msg/', send_msg)
            response = http_conn.getresponse()
            resp_msg = response.read()
            with open('error.html', 'w') as f:
                f.write(resp_msg)
            if 'successful' in resp_msg.lower():
                log.info('send msg to %s successful! msg: %s',
                          server_type, send_msg)
                ret = 'OK'
            else:
                log.error('%s response error, when recv msg: %s',
                          server_type, send_msg)
                ret = 'SERVER_RET_ERR'

            http_conn.close()
            return ret, resp_msg
        except Exception, err:
            log.error('send msg to %s exception, detail: %s. msg: %s',
                      server_type, err, send_msg)
            ret = 'CONN_SERVER_FAILED'
    else:
        log.debug('There is no %s to send msg to.', server_type)
        ret = 'NOT_CONF_SERVER'

    return ret, None

def query_vm_user(vm_id):
    global QUERY_VM_MSG

    send_msg = QUERY_VM_MSG % vm_id
    ret, resp_msg = send_msg_to_server(send_msg, '<tcm server>')
    if ret == 'OK':
        data = resp_msg.strip('\n').split('\n')[1]
        user, ip, port = data.split(':')
        user_info = (user, ip, port)
        return None, user_info
    else:
        return ret, resp_msg
