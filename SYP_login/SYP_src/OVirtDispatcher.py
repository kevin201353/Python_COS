#!usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 Shen Cloud, Inc.
#

"""OVirt dispatch moudle"""

import os
import socket
import logging
import threading
import subprocess
import ConfigParser
import httplib
import time
from threading import Thread
import os.path

from subprocess import Popen
from restsdk import API

log = logging.getLogger(__name__)

MULTICAST_PORTS_MSG = '''<multicast_ports>
    <belong_host>%s</belong_host>
    <user_name>%s</user_name>
    <data_port>%d</data_port>
    <data_xor>%s</data_xor>
</multicast_ports>'''

def check_ip(ipaddr):
    """Is it a ip string format"""

    addr_list = ipaddr.strip().split('.')  # 切割IP地址为一个列表
    if len(addr_list) != 4:  # 切割后列表必须有4个参数
        return False

    for addr in addr_list:
        try:
            addr = int(addr)  # 每个参数必须为数字，否则校验失败
        except:
            return False

        if addr > 255 or addr < 0:  # 每个参数值必须在0-255之间
            return False

    return True

class OVirtDispatcher(object):
    """OVirt dispatch class

    This class is used to login and logout the mainwnd and operate the vms.

    Attributes:
        config: the object of configure read/write by ovirt.
                such as baseurl, enablessl, username, password, etc.
        base_url: the variable to save the http base url.
    """

    api = None

    def __init__(self):
        self.config = ConfigParser.ConfigParser()
        self.config.read('/var/ovirt.conf')
        self.base_url = self.config.get('oVirt', 'BaseUrl')

    def update(self):
        self.base_url = self.config.get('oVirt', 'BaseUrl')

    def syncClock(self):
        """ Sync terminal clock.
        """
        try:
            server_ip = ''
            if self.base_url.count('/'):
                p1 = self.base_url.index('/')
                if self.base_url[p1+2:].count(':'):
                    p2 = self.base_url[p1+2:].index(':')
                    server_ip = self.base_url[p1+2:p1+2+p2]
                    cmd = 'sudo ntpdate %s' % server_ip
                    Popen(cmd, shell=True)
                    Popen('sudo hwclock -w', shell=True)
        except:
            pass

    def login(self, username, password):

        self.syncClock()
        OVirtDispatcher.api = API()
        ret, info = OVirtDispatcher.api.login(url=self.base_url,
                                              username=username,
                                              password=password)
        if ret:
            return True, 'Success'
        else:
            return False, info

    def logout(self):
        if OVirtDispatcher.api:
            OVirtDispatcher.api.logout()
            OVirtDispatcher.api = None

    def get_user_vms(self, vmid=None):
        """Get the list of user virtual machines"""
        try:
            return OVirtDispatcher.api.getVmInfo(vmid=vmid)
        except Exception as e:
            log.error("get_user_vms error: %s" % e)

        return None

    def get_vm_ticket(self, vmid):
        """Get virtual machine's ticket"""
        try:
            return OVirtDispatcher.api.getVmTicket(vmid)
        except Exception as e:
            log.error("get_vm_ticket error: %s" % e)

        return None

    def start_vm(self, vmid):
        """Start virtual machine"""
        try:
            OVirtDispatcher.api.handleVm(vmid, 'start')
        except Exception as e:
            log.error("start_vm error: %s" % e)
        return True, '', ''

    def stop_vm(self, vmid):
        """Stop virtual machine"""
        try:
            OVirtDispatcher.api.handleVm(vmid, 'stop')
        except Exception as e:
            log.error("stop_vm error: %s" % e)
        return True, '', ''

    def shutdown_vm(self, vmid):
        """Shutdown virtual machine"""
        try:
            OVirtDispatcher.api.handleVm(vmid, 'shutdown')
        except Exception as e:
            log.error("shutdown_vm error: %s" % e)
        return True, '', ''

    def listen_spicy(self, domain):
        if os.path.exists("/tmp/data_port") and os.path.exists("/tmp/data_xor"):
            with open('/var/upgrade.info', 'r') as teacher_info_file:
                teacher_str = ''
                teacher_info = teacher_info_file.readlines()
                i = 0
                for info in teacher_info:
                    teacher_str = info.strip()
                    if teacher_str == '<teacher manager>':
                        teacher_str = teacher_info[i+1].strip()
                        break
                    i += 1
                strr = teacher_str.strip()[len('http://'):]
                teacher_server_ip, teacher_server_port = strr.split(':')
            with open('/tmp/data_port', 'r') as port_info_file:
                port_info = port_info_file.readlines()
                for info in port_info:
                    port_str = info.strip()
            port = int(port_str)
            with open('/tmp/data_xor', 'r') as xor_info_file:
                xor_info = xor_info_file.readlines()
                for info in xor_info:
                    xor_str = info.strip()
            user_name = self.config.get('oVirt', 'username').strip()
            try:
                http_conn = httplib.HTTPConnection(teacher_server_ip, teacher_server_port)
            except:
                return True
            send_msg = MULTICAST_PORTS_MSG % (domain, user_name, port, xor_str)
            log.debug('send port and xor to teacher.')
            try:
                http_conn.request('POST', '/client_msg/', send_msg)
                response = http_conn.getresponse()
                resp_msg = response.read()
                if 'successful' in resp_msg.lower():
                    log.debug('send port and xor to teacher successful! ')
                    log.debug(send_msg)
                    cmd = "sudo rm /tmp/data_port"
                    time.sleep(10)
                    #os.system(cmd)
                    subprocess.Popen(cmd, shell=True)
                    cmd = "sudo rm /tmp/data_xor"
                    subprocess.Popen(cmd, shell=True)
                    return False
                else:
                    log.error(resp_msg)
                    return True
            except Exception, err:
                log.error(err)
                return True
            finally:
                http_conn.close()
        else:
            return True

    def listen(self, domain):
        flag = 1
        while flag:
            flag = self.listen_spicy(domain)
            if flag:
                time.sleep(1.0)

    def connect_vm(self, vm, identity_flag):
        """Connect virtual machine"""

        if not vm:
            return False, 'vm is None', ''

        port = vm['port']
        sport = vm['secure_port']
        url = vm['url']
	secret_key = vm['ticket']
        if check_ip(url):
            try:
                host_ip = url
                try:
                    for line in open('/etc/wan_hosts', 'r'):
                        if host_ip == line.split()[0].strip():
                            url = line.split()[1].strip()
                            break
                except:
                    url = socket.gethostbyaddr(url)[0]
                else:
                    url = socket.gethostbyaddr(url)[0]
            except:
                pass
        else:
            host_ip = socket.gethostbyname(url)

        expiry = 7*24*60*60

        if secret_key:
            log.info("connect vm: %s, server_address=%s, port=%s, "
                     "secure_port=%s, key=%s, expiry=%s",
                     vm['name'], url, port, sport, secret_key, expiry)
            connect_msg = ('spicy -h {0} -p {1} -s {2} -w {3} -f'.format(url, port, sport, secret_key))
            log.info(connect_msg)

            with open("/tmp/syp_reconnect", 'w') as f:
                f.write(connect_msg)

            if identity_flag == "teacher":
                cmd = "sudo rm /tmp/data_port"
                os.system(cmd)
                #subprocess.Popen(cmd, shell=True)
                cmd1 = "sudo rm /tmp/data_xor"
                os.system(cmd1)
                #subprocess.Popen(cmd1, shell=True)
                t = Thread(target=self.listen, args=(host_ip,))
                t.setDaemon(True)
                t.start()
            look_spicy_cmd = "ps aux | grep eclass_client | grep -v grep | wc -l"
            look_spicy_pro = Popen(look_spicy_cmd, shell=True, stdout=subprocess.PIPE)
            spicy_pro_nu = int(look_spicy_pro.communicate()[0].strip())
            if spicy_pro_nu > 0:
                detail = "teacher is teaching by using your computer"
                return 0xfffffffe, detail, None
            else:
                cmd = 'spicy -h {0} -p {1} -s {2} -w {3} -f'.format(url, port, sport, secret_key)
                ret_code = subprocess.call(cmd, shell=True)
            if ret_code:
                if ret_code == -9:
                    detail = 'drop conn vm'
                else:
                    detail = 'Bad request'
                log.error("call spicy to connect vm failed! retcode=%s.", ret_code)
                return False, detail, 'call spicy to connect vm failed'
            return True, secret_key, expiry
        else:
            log.error('connect vm %s failed. reason: %s. detail: %s.',
                      vm['name'], secret_key, expiry)
            return False, secret_key, expiry


if '__main__' == __name__:
    test = OVirtDispatcher()
    # test login
    test.login(username='admin@internal', password='Amd64bit', enable_ssl=True)

    test.get_user_name()
