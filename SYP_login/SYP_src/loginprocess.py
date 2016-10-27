#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 ShenCloud Inc.

"""loginproess module"""

import time
import logging
import threading
import subprocess
from threading import Thread
from multiprocessing import Process, Pipe
import socket
import select
import os
import re
import xmlrpclib
import httplib
import urllib2

import ConfigParser
from OVirtDispatcher import OVirtDispatcher
import basictools as bt
from urlparse import urlsplit
import serverprocess as tcm
from customtimer import CustomTimer, StoppableThread
import ifconfig
from IPy import IP
from threadpool import ThreadPool

log = logging.getLogger(__name__)

BEGIN_CLASS = '''<begin_class>%s</begin_class>'''
FINISH_CLASS_FILE = "/tmp/finish_class"

POWEROFF_MSG = '''<shell_cmd>
    <sender>%s</sender>
    <reciever></reciever>
    <cmd>%s</cmd>
</shell_cmd>'''

UPGRADE_INFO = '/var/upgrade.info'


class LoginProcess(Process):

    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
        super(LoginProcess, self).__init__()
        (self.conn_send, self.conn_recv,
         self.setting_conn_send, self.setting_conn_recv,
         self.refresh_conn_send, self.refresh_conn_recv,
         self.update_vms_send, self.update_vms_recv,
         self.rpc_recv, self.rpc_send,
         self.rpc_vm_recv, self.rpc_vm_send,
         self.__pwdkey) = args
        self.__ovirtconnect = OVirtDispatcher()
        self.config = self.__ovirtconnect.config
        self.settings = ConfigParser.ConfigParser()
        #self.vms_list = None
        self.vms_list_store = []
        self.vms_send = []
        #self.last_time = 0
        #self.new_time = 0
        self.user = ''
        self.admin = False
        self.upgrade_list = []
        self.connect_thread = None
        self.refresh_process = None
        self.refresh_thread = None
        self.checkupgrade_process = None
        self.apply_conn_process = None
        #self.get_vm_stop = False
        self.stop_refresh = False
        self.connected_vm = False
        self.drop_connect = False
        self.update_vms_timer = None
        self.relogin_timer = None

        self.login_thread = None
        self.login_recv, self.child_login_send = Pipe()

        self.mutex_conn_send = threading.Lock()
        self.mutex_setting_conn_send = threading.Lock()
        self.mutex_start = threading.Lock()
        self.mutex_shutdown = threading.Lock()
        self.mutex_stop = threading.Lock()
        self.mutex_refresh_conn_send = threading.Lock()
        self.mutex_ovirt = threading.Lock()
        self.mutex_vms_list = threading.Lock()
        self.mutex_query_conn = threading.Lock()
        # add by zhanglu
        self.mutex_rpc_send = threading.Lock()
        self.mutex_rpc_recv = threading.Lock()
        self.mutex_rpc_vm_send = threading.Lock()
        self.mutex_rpc_vm_recv = threading.Lock()
        self.connect_timeout = False
        # end

    def find_server(self):
        self.cur_net_segment = self.calc_netsegment()
        while not self.cur_net_segment:
            time.sleep(3)
            self.cur_net_segment = self.calc_netsegment()

        server_ip = self.get_conf()
        log.info("current network segment is: %s" % self.cur_net_segment)
        log.info("server information in config file is: %s" % server_ip)

        def get_server_ip():
            while True:
                server = self.grab_server()
                if server:
                    break
                else:
                    time.sleep(3)
            return server

        if not server_ip:
            server = get_server_ip()
        elif server_ip == "sycos.shencloud.com":
            server = get_server_ip()
        else:
            server_net_segment = IP(server_ip).make_net(self.netmask)
            if server_net_segment != self.cur_net_segment:
                server = get_server_ip()
            else:
                return
        log.info("server's ip is: %s" % server)
        if server:
            self.change_conf(server)

    def calc_netsegment(self):
        """calculate the current ip's network segment"""
        self.cur_ip = self.netmask = None
        for iter_ in ifconfig.list_ifs():
            curif = ifconfig.find_if_by_name(iter_)
            if (not curif.name.startswith('wlan')) \
               or curif.name != 'lo':
                if curif.is_up():
                    self.cur_ip = curif.get_ip()
                    self.netmask = curif.get_netmask()[1]
                    if self.cur_ip:
                        break
        if self.cur_ip and self.netmask:
            log.info("current network information, ip: %s , netmask: %s" % (self.cur_ip, self.netmask))
            network_segment = IP(self.cur_ip).make_net(self.netmask)
            return network_segment
        return None

    def get_conf(self):
        """get the server's ip in confige file: /var/ovirt.conf and /var/upgrade.info"""
        base_url = self.config.get('oVirt', 'BaseUrl')
        base_server = None
        if base_url.count('/'):
            p1 = base_url.index('/')
            if base_url[p1+2:].count(':'):
                p2 = base_url[p1+2:].index(':')
                base_server = base_url[p1+2:p1+2+p2]

        if not base_server:
            log.error("Not set the server ip")
            return None

        with open(UPGRADE_INFO, 'r') as upgrade_info_file:
            mode = ''
            upgrade_str = ''
            upgrade_info = upgrade_info_file.readlines()
            i = 0
            for info in upgrade_info:
                upgrade_str = info.strip()
                if upgrade_str == '<server mode>':
                    mode = upgrade_info[i+1].split(':')[1].strip()
                    break
                i += 1

            i = 0
            for info in upgrade_info:
                upgrade_str = info.strip()
                if upgrade_str == '<tcm server>':
                    upgrade_str = upgrade_info[i+1].strip()
                    break
                i += 1
            strr = upgrade_str.strip()[len('http://'):]
            server_ip, server_port = strr.split(':')

        if not base_server or not server_ip:
            return None

        return base_server

    def grab_server(self):
        """if we don't the server's ip, we should grab the server's ip information form ip 254 to ip 2"""
        num_threads = 10

        ips = [i for i in xrange(2, 255)]
        ips.reverse()

        perfix_origin = self.cur_net_segment.net().strNormal()
        perfix = '.'.join(perfix_origin.split('.')[0:3]) + '.'

        server = None
        circle_num = 253/num_threads + int(253%num_threads!=0)
        for i in xrange(circle_num):
            start = i * num_threads
            end = start + num_threads

            pool = ThreadPool(num_threads=num_threads)
            for ip in ips[start:end]:
                pool.add_task(self.get_server, perfix + str(ip))
            pool.destroy()
            results = pool.show_results()
            for ip in results:
                if ip:
                    server = ip
                    break
            if server:
                break
        log.info("current server's ip we grab is: %s" % server)
        return server

    def get_server(self, server):
        log.debug("get server info from %s" % server)
        try:
            x = urllib2.urlopen('http://' +  server+ ':80', timeout=3)
            x = urllib2.urlopen('https://' +  server+ ':443', timeout=3)
        except:
            return None

        return server

    def change_conf(self, server):
        """write server's ip into confige file: /var/ovirt.conf and /var/upgrade.info"""
        self.config.set('oVirt', 'BaseUrl', "https://"+server+":443/ovirt-engine/api")
        with open('/var/ovirt.conf', 'w') as f:
            self.config.write(f)

        with open(UPGRADE_INFO, 'r') as file_read:
            upgrade_info = file_read.readlines()
            with open(UPGRADE_INFO, 'w') as file_write:
                mode_line = 1
                server_line = 4
                i = 0
                for info in upgrade_info:
                    upgrade_str = info.strip()
                    if upgrade_str == '<server mode>':
                        mode_line = i + 1
                    elif upgrade_str == '<tcm server>':
                        server_line = i + 1
                    i += 1

                upgrade_info[mode_line] = 'mode:   user_defined\n'
                if ':' in server:
                    upgrade_info[server_line] = 'http://%s\n' % server
                else:
                    upgrade_info[server_line] = 'http://%s:8000\n' % server
                file_write.writelines(upgrade_info)

        self.save_teacher_url(server)

    def save_teacher_url(self, url):
        """save teacher url to file:/var/upgrade.info"""
        with open(UPGRADE_INFO, 'r') as file_read:
            teacher_info = file_read.readlines()
            with open(UPGRADE_INFO, 'w') as file_write:
                i = 0
                for info in teacher_info:
                    teacher_str = info.strip()
                    if teacher_str == '<teacher manager>':
                        i += 1
                        break
                    i += 1
                line = i
                if ':' in url:
                    teacher_info[line] = 'http://%s\n' % (url)
                else:
                    teacher_info[line] = 'http://%s:8090\n' % (url)
                file_write.writelines(teacher_info)

    def run(self):

        self.poller = select.poll()
        self.poller.register(self.conn_recv.fileno(), select.POLLIN)
        self.poller.register(self.setting_conn_recv.fileno(), select.POLLIN)
        self.poller.register(self.refresh_conn_recv.fileno(), select.POLLIN)
        self.poller.register(self.update_vms_recv.fileno(), select.POLLIN)
        self.poller.register(self.login_recv.fileno(), select.POLLIN)
        # add by zhanglu
        self.poller.register(self.rpc_recv.fileno(), select.POLLIN)
        self.poller.register(self.rpc_vm_recv.fileno(), select.POLLIN)

        # self.threads = []
        t = Thread(target=self.find_server)
        t.setDaemon(True)
        t.start()

        while 1:
            events = self.poller.poll()
            for fd, event in events:
                if fd == self.rpc_recv.fileno() and event & select.POLLIN:
                    msg_type, msg_data = self.rpc_recv.recv()
                    if msg_type == "waitting_ad":
                        log.info('recv waitting_ad msg in run.')
                        t = Thread(target=self.waitting_ad)
                        t.setDaemon(True)
                        t.start()

                elif fd == self.conn_recv.fileno() and event & select.POLLIN:
                    msg_type, msg_data = self.conn_recv.recv()
                    if msg_type == "waitting_server_up":
                        log.info('recv waitting_server_up msg in run.')
                        t = Thread(target=self.waitting_server_up)
                        t.setDaemon(True)
                        t.start()

                    elif msg_type == 'login':
                        log.info("rec login msg")
                        self.stop_refresh = False

                        self.login_thread = StoppableThread(target=self.wait_login_return,
                                args=(msg_type, msg_data, self.child_login_send))
                        self.login_thread.start()

                    elif msg_type == 'login_terminate':
                        log.info('recv login_terminate msg.')
                        if self.login_thread and self.login_thread.is_alive():
                            self.login_thread.terminate()
                            self.login_thread = None

                    elif msg_type == 'check_autologin':
                        self.save_autologin(msg_data[0])
                    elif msg_type == 'check_storepwd':
                        self.save_storepwd(msg_data[0])
                    elif msg_type == 'login_conf':
                        try:
                            self.mutex_conn_send.acquire()
                            self.conn_send.send((msg_type, self.login_config()))
                        finally:
                            self.mutex_conn_send.release()
                    elif msg_type == 'exit':
                        return
                elif fd == self.login_recv.fileno() and event & select.POLLIN:
                    msg_type, msg_data = self.login_recv.recv()
                    if msg_type == 'login_return':
                        log.info("recv login_return msg")
                        msg_type, msg_data, ret, info, vmList= msg_data
                        self.base_url = self.__ovirtconnect.base_url
                        username, passwd = msg_data
                        try:
                            self.mutex_conn_send.acquire()
                            self.conn_send.send((msg_type, (ret, self.__ovirtconnect.base_url, info, vmList)))
                        finally:
                            self.mutex_conn_send.release()

                        if ret:
                            self.user = username
                            if self.user.startswith('admin'):
                                self.admin = True
                            else:
                                t = Thread(target=self.send_user_vms,
                                           args=(self.user,))
                                t.setDaemon(True)
                                t.start()

                            self.login_ok(username, passwd)

                elif fd == self.setting_conn_recv.fileno() and event & select.POLLIN:
                    msg_type, msg_data = self.setting_conn_recv.recv()
                    if msg_type == 'load_config':
                        try:
                            self.mutex_setting_conn_send.acquire()
                            self.setting_conn_send.send((msg_type, self.load_config()))
                        finally:
                            self.mutex_setting_conn_send.release()
                    elif msg_type == 'save_config':
                        self.save_config(msg_data)
                        try:
                            self.__ovirtconnect.update()
                        except:
                            continue
            else:
                pass

    def wait_login_return(self, msg_type, msg_data, msg_send):
        err_table = {"Success":'登录成功',
                     "Invalid":'无效用户名或密码',
                     "Timeout":'登录超时',
                     "Request":'登录请求出错',
                     "Connection":'登录连接出错',
                     "Exception":'登录出错'}

        username, passwd = msg_data
        cnt = 0
        self.__ovirtconnect.update()
        while True:
            ret, info = self.__ovirtconnect.login(username=username, password=passwd)
            cnt += 1
            if ret or info == "Invalid" or cnt > 30:
                break
            else:
                log.debug("login failed info: %s, try again %s" % (info, cnt))
                self.__ovirtconnect.logout()
                time.sleep(3)

        vmList = None
        if username.startswith('admin') and ret:
            while True:
                vmList = self.__ovirtconnect.get_user_vms()
                if vmList == None:
                    time.sleep(2)
                    continue
                else:
                    break
        msg_send.send(('login_return', (msg_type, msg_data, ret, err_table[info], vmList)))

    # add by zhanglu
    def get_server_ip(self):
        self.base_url = self.config.get('oVirt', 'baseurl')

        server_ip = ''
        if self.base_url.count('/'):
            p1 = self.base_url.index('/')
            if self.base_url[p1+2:].count(':'):
                p2 = self.base_url[p1+2:].index(':')
                server_ip = self.base_url[p1+2:p1+2+p2]

        return server_ip

    def waitting_server_up(self):
         ret = ifconfig.ping_server()
         while not ret:
             time.sleep(2)
             ret = ifconfig.ping_server()
         # if there is autologin, put it here
         code = None
         server_ip = self.get_server_ip()
         if server_ip:
             while code != 200:
                 try:
                     response = urllib2.urlopen('http://' + server_ip + ':80', timeout=4)
                     code = response.getcode()
                 except Exception as e:
                     log.error("send get request to server failed! %s" % e)
                     code = None

         try:
             self.mutex_conn_send.acquire()
             self.conn_send.send(("waitting_server_up", ret))
         finally:
             self.mutex_conn_send.release()

    def waitting_ad(self):
        ret = False
        while not ret:
            time.sleep(1)
            server_ip = self.get_server_ip()
            server = xmlrpclib.ServerProxy("http://%s:8011/" % server_ip)
            try:
                result = server.waiting_ad()
                log.debug("waitting_ad return: " + str(result))
                if "successful" in result:
                    ret = True
            except Exception as err:
                log.error("ad hava not up! detail: " + str(err))
                ret = False
        try:
            self.mutex_rpc_send.acquire()
            self.rpc_send.send(("waitting_ad", ret))
        finally:
            self.mutex_rpc_send.release()

    def on_startall_vms(self):
        """启动所有虚拟机"""
        log.info("try to start all vms")
        server_ip = self.get_server_ip()
        ret = None
        try:
            server = xmlrpclib.ServerProxy("http://%s:8011/" % server_ip)
            ret = server.start_all_vms()
        except Exception as e:
            log.error("call rpc function: start_al_vms failed, detail: " + str(e))
        try:
            self.mutex_conn_send.acquire()
            self.conn_send.send(("start_all", ret))
        finally:
            self.mutex_conn_send.release()

    def close_server(self):
        """关闭服务器"""
        server_ip = self.get_server_ip()
        server = xmlrpclib.ServerProxy("http://%s:8011/" % server_ip)
        ret = False
        try:
            ret = server.shutdown_all()
        except:
            pass

        while ifconfig.ping_test(server_ip):
            time.sleep(1)

        try:
            self.mutex_rpc_send.acquire()
            log.info("shutdown server successed!")
            self.rpc_send.send(("waitting_server_down", ret))
        finally:
            self.mutex_rpc_send.release()

    def on_shutdownall(self, teacher=False, restart=False):
         """关闭所有虚拟机除了TCM、和服务器"""
         server_ip = self.get_server_ip()
         server = xmlrpclib.ServerProxy("http://%s:8011/" % server_ip)
         ret = server.shutdown_vms_exclude_visual_server(teacher, restart)
         if ret:
             return False
         return True

    def login_ok(self, username, passwd):
        if self.admin:
            self.start_relogin(username, passwd)
        while 1:
            events = self.poller.poll()
            for fd, event in events:
                if fd == self.rpc_vm_recv.fileno() and event & select.POLLIN:
                    msg_type, msg_data = self.rpc_vm_recv.recv()
                    if msg_type == 'start_all':
                        log.info('recv startall vm msg in login_ok.')
                        t = Thread(target=self.on_startall_vms)
                        t.setDaemon(True)
                        t.start()
                    elif msg_type == "restart_vm":
                        log.info("recv shutdown_vm msg in login_ok")
                        t = Thread(target=self.on_shutdownall, args=(True,True))
                        t.setDaemon(True)
                        t.start()
                    elif msg_type == "shutdown_vm_term":
                        log.info("recv shutdown_vm msg in login_ok")
                        t = Thread(target=self.on_shutdownall, args=(True,))
                        t.setDaemon(True)
                        t.start()

                elif fd == self.conn_recv.fileno() and event & select.POLLIN:
                    msg_type, msg_data = self.conn_recv.recv()
                    if msg_type == 'storepwd':
                        log.info("recv storepwd msg in login_ok")
                        (username, passwd) = msg_data
                        # 登录成功后，也将账号密码保存在历史登录用户列表里面，但是注意不要重复
                        user_list = get_user_list("/var/users.conf")
                        if user_list:
                            for user in user_list:  # 删除重复的用户
                                 if username == user["username"]:
                                      user_list.remove(user)
                        current_user = {"username": username, "password": bt.encrypt(self.__pwdkey, passwd)}
                        user_list.insert(0, current_user)  # 将此时登录的用户放在第一个
                        with open("/var/users.conf", "w") as user_list_file:
                            for user in user_list:
                                user_list_file.write(user["username"]+"\t"+user["password"]+"\n")
                        self.__ovirtconnect.config.set('oVirt', 'username', username)
                        self.__ovirtconnect.config.set('oVirt', 'password',
                                                       bt.encrypt(self.__pwdkey, passwd))
                        with open('/var/ovirt.conf', 'w') as f:
                            self.__ovirtconnect.config.write(f)
                    elif msg_type == 'start':
                        log.info('recv start vm msg in login_ok.')
                        vm_name, vm_id = msg_data
                        t = Thread(target=self.start_vm, args=(vm_name, vm_id,))
                        t.setDaemon(True)
                        t.start()

                    elif msg_type == "shutdown_server":
                        log.info('recv shutdown server msg in login_ok.')
                        t = Thread(target=self.close_server)
                        t.setDaemon(True)
                        t.start()

                    elif msg_type == "terminate_demon":
                        log.info('recv terminate_demon msg in login_ok.')
                        t = Thread(target=self.terminate_demon)
                        t.setDaemon(True)
                        t.start()

                    elif msg_type == "stu_auto_connect":
                        log.info('recv stu_auto_connect msg in login_ok.')
                        t = Thread(target=self.http_send_auto_connect)
                        t.setDaemon(True)
                        t.start()

                    elif msg_type == "poweroff_stu":
                        log.info('recv poweroff_stu msg in login_ok.')
                        t = Thread(target=self.http_send_poweroff_stu)
                        t.setDaemon(True)
                        t.start()

                    elif msg_type == 'shutdown':
                        log.info('recv shutdown vm msg in login_ok.')
                        vm_name, vm_id = msg_data
                        t = Thread(target=self.shutdown_vm, args=(vm_name, vm_id,))
                        t.setDaemon(True)
                        t.start()

                    elif msg_type == 'stop':
                        log.info('recv stop vm msg in login_ok.')
                        vm_name, vm_id = msg_data
                        t = Thread(target=self.stop_vm, args=(vm_name, vm_id,))
                        t.setDaemon(True)
                        t.start()

                    elif msg_type == "timeout":
                        log.info('recv timeout msg in login_ok.')
                        self.connect_timeout = True

                    elif msg_type == 'connect':
                        log.info('recv connect vm msg in login_ok.')
                        self.stop_update_vms()

                        vm_id, identity_flag = msg_data
                        self.connect_timeout = False
                        self.connect_thread = StoppableThread(target=self.connect_vm,
                                                      args=(self.conn_send,
                                                            identity_flag,
                                                            vm_id))
                        self.connect_thread.start()

                    elif msg_type == 'stop_connect':
                        log.info("recv stop_connect msg in login_ok")
                        self.stop_connect_vm()
                    elif msg_type == 'check_autologin':
                        log.info("recv check_autologin msg in login_ok")
                        self.save_autologin(msg_data[0])
                    elif msg_type == 'check_storepwd':
                        log.info("recv check_storepwd msg in login_ok")
                        self.save_storepwd(msg_data[0])
                    elif msg_type == 'login_conf':
                        log.info("recv login_conf msg in login_ok")
                        try:
                            self.mutex_conn_send.acquire()
                            self.conn_send.send((msg_type, self.login_config()))
                        finally:
                            self.mutex_conn_send.release()

                    elif msg_type == 'shutdown_logout':
                        log.info('recv shutdown_logout msg in login_ok.')
                        vm_name, vm_id = msg_data
                        self.shutdown_vm(vm_name, vm_id)
                        self.stop_connect_vm()
                        self.stop_refresh_vms()
                        self.stop_update_vms()
                        self.__ovirtconnect.logout()
                        return

                    elif msg_type == 'logout':
                        log.info('recv logout msg in login_ok.')
                        self.stop_relogin()
                        self.stop_refresh_vms()
                        self.stop_connect_vm()
                        self.stop_update_vms()
                        self.__ovirtconnect.logout()
                        return

                    elif msg_type == 'query_vm':
                        log.info('recv query vm msg in login_ok.')
                        vm_id, vm_name = msg_data
                        t = Thread(target=self.query_vm, args=(vm_id, vm_name))
                        t.start()

                    elif msg_type == 'apply_conn':
                        log.info('recv apply conn msg in login ok.')
                        user_info, vm_name = msg_data
                        self.apply_conn_process = Process(target=self.apply_conn,
                                                          args=(user_info, vm_name))
                        self.apply_conn_process.start()

                    elif msg_type == 'drop_conn':
                        log.info("recv drop_conn msg in login_ok")
                        self.proc_drop_conn()

                elif fd == self.setting_conn_recv.fileno() and event & select.POLLIN:
                    msg_type, msg_data = self.setting_conn_recv.recv()
                    if msg_type == 'load_config':
                        log.info("recv load_config msg in login_ok")
                        try:
                            self.mutex_setting_conn_send.acquire()
                            self.setting_conn_send.send((msg_type, self.load_config()))
                        finally:
                            self.mutex_setting_conn_send.release()
                    elif msg_type == 'save_config':
                        log.info("recv save_config msg in login_ok")
                        self.save_config(msg_data)
                        try:
                            self.__ovirtconnect.update()
                        except:
                            continue
                elif fd == self.refresh_conn_recv.fileno() and event & select.POLLIN:
                    msg_type, msg_data = self.refresh_conn_recv.recv()
                    if msg_type == 'refresh':
                        user =  msg_data
                        log.info('sub process recv refresh cmd, user: %s', user)
                        self.refresh_thread = Thread(target=self.refresh_vms,
                                                     args=(user, self.refresh_conn_send))
                        self.refresh_thread.start()
                    elif msg_type == 'stop_refresh':
                        log.info("recv stop_refresh msg in login_ok")
                        self.stop_refresh_vms()

                elif fd == self.update_vms_recv.fileno() and event & select.POLLIN:
                    msg_type, msg_data = self.update_vms_recv.recv()
                    if msg_type == 'update_vms':
                        log.info('recv update_vms msg in login ok.')
                        self.start_update_vms(msg_data)
            else:
                pass


    def relogin(self, username, passwd):
        log.debug("Relogin '%s'" % username)

        self.__ovirtconnect.logout()
        self.__ovirtconnect.login(username=username, password=passwd)
        return True

    def start_relogin(self, username, passwd):
        log.debug("start relogin '%s'" % username)
        if not self.relogin_timer:
            self.relogin_timer = CustomTimer(3600, self.relogin, args=[username, passwd])
            self.relogin_timer.start()

    def stop_relogin(self):
        log.debug("stop relogin")
        if self.relogin_timer:
            self.relogin_timer.stop()
            self.relogin_timer = None

    def query_vm(self, vm_id, vm_name):
        self.drop_connect = False
        self.mutex_query_conn.acquire()
        try:
            ret, user_info = tcm.query_vm_user(vm_id)
        except Exception, err:
            ret = None
        finally:
            self.mutex_query_conn.release()

        if ret:
            err_code = tcm.err_code[ret]
        else:
            err_code = None

        if not self.drop_connect:
            self.mutex_conn_send.acquire()
            try:
                self.conn_send.send(('query_vm', (ret, user_info, err_code)))
            except Exception, err:
                log.error('return query vm result to main failed.')
            finally:
                self.mutex_conn_send.release()
        self.drop_connect = False

    def apply_conn(self, user_info, vm_name):
        user_name, user_ip, user_port = user_info
        address = (user_ip, int(user_port))
        send_msg = 'admin_connect\n%s' % vm_name

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(address)
            sock.send(send_msg.strip('\n'))
            data = sock.recv(1024)
        except Exception, err:
            log.error('connect to user %s %s:%s error when connect vm, %s',
                      user_name, user_ip, user_port, err)
            self.mutex_conn_send.acquire()
            try:
                self.conn_send.send(('apply_conn', (False, None)))
            except Exception, err:
                log.error('return query vm result to main failed.')
            finally:
                self.mutex_conn_send.release()
            return
        finally:
            sock.close()

        self.conn_send.send(('apply_conn', (True, data)))

    def terminate_demon(self):
        """terminate the teacher's demon to student's computer
        """

        try:
            username = re.search(r"(.*?)@.*?", self.user).group(1)
        except Exception as err:
            log.error("An error in get username: %s" % str(err))
            return False
        path = "/demonstrate_stop?hostname=%s" % username
        ret = self.send_request_teaServer("GET", path)

        return not ret

    def http_send_auto_connect(self):
        """send the POST request to tell student's conputer auto to conenct vm"""

        sn = self.get_sn_msg()
        body = BEGIN_CLASS % (sn)
        path = '/client_msg/'
        method = "POST"
        self.send_request_teaServer(method, path, body)

    def get_sn_msg(self):
        #
        # 获取当前的客户端信息 IP, MAC, SN(序列号)
        #
        cur_ip = cur_mac = cur_sn = ''
        # get ip and mac
        for iter_ in ifconfig.list_ifs():
            curif = ifconfig.find_if_by_name(iter_)
            if curif.is_up():
                # cur_ip = curif.get_ip()
                cur_mac = curif.get_mac()

        return cur_mac


    def http_send_poweroff_stu(self):
        """send the POST request to shutdown all computer of student
        """

        body = POWEROFF_MSG % (self.user, 'poweroff')
        path = '/client_msg/'
        method = "POST"
        self.send_request_teaServer(method, path, body)

    def send_request_teaServer(self, method="GET", path="/", body=None):
        """send a request to teacher server
        """
        server_ip, server_port = self.get_tea_server()
        log.info("teacher server's ip: %s, port is: %s" % (server_ip, server_port))
        try:
            http_conn = httplib.HTTPConnection(server_ip, server_port)
        except Exception, err:
            log.error("An error in connecte to teacher server, reason: %s" % err)
            return True
        #send_msg = POWEROFF_MSG % (self.user, 'poweroff')
        timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(3.0)
        try:
            http_conn.request(method, path, body)
            response = http_conn.getresponse()
            resp_msg = response.read()
            if 'successful' in resp_msg.lower():
                log.debug('send msg to teacher manager successful!')
                return True
            else:
                log.error(resp_msg)
        except Exception, err:
            log.error("send msg to teacher serve faild! reason: %s" % err)
        finally:
            http_conn.close()
            socket.setdefaulttimeout(timeout)

        return False

    def get_tea_server(self):
        """
        get teacher server's IP and PORT
        """
        with open('/var/upgrade.info', 'r') as upgrade_info_file:
            upgrade_info = upgrade_info_file.read()
        try:
            server_info = re.search(r"<teacher manager>\n(.*?)\n", upgrade_info).group(1)
            re_server = re.search(r"http://(.*?):(\d+)", server_info)
            server_ip, server_port = re_server.groups()
        except Exception, err:
            log.error("An error in get teacher server! reason: %s" % err)
            server_ip, server_port = "", ""

        return server_ip, server_port

    def proc_drop_conn(self):
        self.drop_connect = True
        if self.apply_conn_process:
            if self.apply_conn_process.is_alive():
                self.apply_conn_process.terminate()
            self.apply_conn_process = None

    def start_update_vms(self, update_interval):
        log.info("start update vms timer start")
        self.stop_update_vms()
        self.update_vms_timer = CustomTimer(update_interval, self.update_vms_bg)
        self.update_vms_timer.start()

    def stop_update_vms(self):
        if self.update_vms_timer:
            self.update_vms_timer.stop()
            self.update_vms_timer = None

    def start_vm(self, vm_name, vm_id):

        log.info('run start_vm thread.')

        try:
            self.mutex_ovirt.acquire()
            retcode, reason, detail = self.__ovirtconnect.start_vm(vm_id)
        except:
            return
        finally:
            self.mutex_ovirt.release()

        if not retcode:
            log.error('user: %s start vm: %s failed. reason: %s. detail: %s.',
                      self.user, vm_name, reason, detail)
        else:
            log.info("user: %s start the vm: %s success",
                     self.user,
                     vm_name)

    def shutdown_vm(self, vm_name, vm_id):
        """关闭虚拟机"""
        # msg_type = 'shutdown'
        log.info('run shutdown_vm thread.')

        try:
            self.mutex_ovirt.acquire()
            retcode, reason, detail = self.__ovirtconnect.shutdown_vm(vm_id)
        except:
            return
        finally:
            self.mutex_ovirt.release()

        if not retcode:
            log.error('user: %s shutdown vm: %s failed. reason: %s. detail: %s.',
                      self.user, vm_name, reason, detail)
        else:
            log.info("user: %s shutdown the vm: %s success",
                     self.user,
                     vm_name)

    def stop_vm(self, vm_name, vm_id):
        msg_type = 'stop'

        log.info('run stop_vm thread.')

        try:
            self.mutex_ovirt.acquire()
            retcode, reason, detail = self.__ovirtconnect.stop_vm(vm_id)
        except:
            return
        finally:
            self.mutex_ovirt.release()

        if not retcode:
            log.error('user: %s stop vm: %s failed. reason: %s. detail: %s.',
                      self.user, vm_name, reason, detail)
        else:
            log.info("user: %s stop the vm: %s success",
                     self.user,
                     vm_name)

    def on_force_kill_vm(self, vmname):
         server_ip = self.get_server_ip()
         server = xmlrpclib.ServerProxy("http://%s:8011/" % server_ip)
         ret = server.force_kill_vm(vmname)
         if ret:
             return False
         return True

    def waitVmPoweringUp(self, vmId):
        vmDict = self.__ovirtconnect.get_user_vms(vmId)
        if not vmDict:
            log.debug("Get vms empty, again")
            time.sleep(1)
            return None
        elif type(vmDict) is list:
            vmDict = vmDict[0]
            vmId = vmDict['id']

        if vmDict['state'] == "down":
            self.__ovirtconnect.start_vm(vmDict['id'])
            time.sleep(2)  # 等待启动
        elif (vmDict['state'] == "powering_up" or
              vmDict['state'] == "up"):
            vmDict['ticket'] = self.__ovirtconnect.get_vm_ticket(vmId)
            if vmDict['ticket']:
                return vmDict
            time.sleep(2)
        elif (vmDict['state'] == "unknown" or
              vmDict['state'] == "not_responding"):
            log.debug("Vm '%s' state '%s' force kill" % (vmDict['name'], vmDict['state']))
            self.on_force_kill_vm(vmDict['name'])
            time.sleep(2)
        else:
            log.debug("try to connect [%s] [%s]" % (vmDict['name'], vmDict['state']))
            time.sleep(5)

        return None

    def connect_vm(self, conn_send, identity_flag, vm_id=None):
        log.info('run connect_vm thread.')
        msg_type = 'connect'

        while not self.connect_timeout:
            vmDict = self.waitVmPoweringUp(vm_id)
            if vmDict:
                self.connected_vm = True
                break

        if not self.connect_timeout:
            try:
                connect_vm_name = vmDict["name"]
                self.config.read('/var/ovirt.conf')
                self.config.set('oVirt', 'vm_name', connect_vm_name)
                with open('/var/ovirt.conf', 'w') as f:
                    self.config.write(f)
                log.debug("start to connect vm")
                (retcode, detail, _) = self.__ovirtconnect.connect_vm(vmDict,
                                                                      identity_flag)
                log.debug("exit connect to vm")
                if not retcode:
                    log.error('connect vm %s failed, detail: %s.',
                              vmDict['name'], detail)
            except NameError, err:
                retcode = 10
                detail = err
                log.error('__ovirtconnect.connect_vm failed! id=%s, detail: %s', vm_id, err)
            except Exception, err:
                log.error('__ovirtconnect.connect_vm failed! id=%s, detail: %s', vm_id, err)
                detail = err
                retcode = 0xffffffff
            finally:
                self.connected_vm = False
        else:
            retcode = 0xfffffffd
            detail = "timeout"
            self.connect_timeout = False
            log.info("Connect timeout")

        if not vmDict:
            conn_send.send((msg_type, (vm_id, retcode, detail, None)))
        else:
            log.debug("send msg: connect to main process.")
            conn_send.send((msg_type, (vm_id, retcode, detail, vmDict['name'])))
        #self.get_vm_stop = False
        #self.last_time = time.time()

    def stop_connect_vm(self):

        if self.connect_thread and self.connect_thread.is_alive():
            log.info("terminate connect_thread")
            self.connect_thread.terminate()
            self.connect_thread = None

        if self.connected_vm:
            log.info("kill spicy process.")
            subprocess.call("sudo kill -9 `ps -ef | grep spicy | grep -v grep | awk '{print $2}'` > /dev/null 2>&1",
                            shell=True)
            self.connected_vm = False

    def refresh_vms(self, user, conn_send):
        # new process should stop the update_vms_timer
        self.mutex_ovirt.acquire()
        try:
            self.refresh_process = Process(target=self.refresh_vms_process,
                                           args=(user,
                                                 conn_send,
                                                 self.__ovirtconnect))
            self.refresh_process.start()
            self.refresh_process.join()
        finally:
            log.debug('refresh vms process completed.')
            self.mutex_ovirt.release()

        return True

    def refresh_vms_process(self, user, conn_send, ovirt_connect):
        msg_type = 'refresh'
        vms_list = ovirt_connect.get_user_vms()

        self.vms_send = []
        tcm_vms_list = []
        for vm in vms_list:
            self.vms_send.append(vm)
            id, name = vm['id'], vm['name']
            tcm_vms_list.append({'id':id, 'name':name, 'user': user})

        conn_send.send((msg_type, (self.vms_send,)))
        try:
            if not user.startswith('admin@'):
                tcm.send_user_vms(tcm_vms_list)
        except:
            pass

    def send_user_vms(self, user):
        vms_list = self.__ovirtconnect.get_user_vms()
        tcm_vms_list = []
        for vm in vms_list:
            id, name = vm['id'], vm['name']
            tcm_vms_list.append({'id':id, 'name':name, 'user': user})
        try:
            tcm.send_user_vms(tcm_vms_list)
        except:
            pass

    def stop_refresh_vms(self):
        self.stop_refresh = True
        if self.refresh_process:
            if self.refresh_process.is_alive():
                self.refresh_process.terminate()
            self.refresh_process = None

    def update_vms_bg(self):
        log.debug('update vms background in loginprocess.')
        self.vms_list_store = self.__ovirtconnect.get_user_vms()
        self.update_vms_send.send(('update_vms', (self.vms_list_store,)))

        return True


    def save_autologin(self, toggled):
        if toggled:
            self.config.set('oVirt', 'autologin', 'True')
            self.config.set('oVirt', 'storepwd', 'True')
        else:
            self.config.set('oVirt', 'autologin', 'False')

        with open('/var/ovirt.conf', 'w') as f:
            self.config.write(f)

    def save_storepwd(self, toggled):
        if toggled:
            self.config.set('oVirt', 'storepwd', 'True')
        else:
            self.config.set('oVirt', 'autologin', 'False')
            self.config.set('oVirt', 'storepwd', 'False')

        with open('/var/ovirt.conf', 'w') as f:
            self.config.write(f)

    def login_config(self):
        self.config.read('/var/ovirt.conf')
        auto_login = self.config.get('oVirt', 'autologin')
        storepwd = self.config.get('oVirt', 'storepwd')
        # str2bool function str lower in "true" "t" "1" "yes" "y"
        auto_login = bt.str2bool(auto_login)
        storepwd = bt.str2bool(storepwd)
        username = self.config.get('oVirt', 'Username')
        if storepwd:
            passwd = self.config.get('oVirt', 'Password')
        else:
            passwd = ''
        # add by zhanglu
        user_list = get_user_list("/var/users.conf")

        return (auto_login, storepwd, username, passwd, user_list)

    def load_config(self):
        self.config.read('/var/ovirt.conf')
        base_url = self.config.get('oVirt', 'BaseUrl')
        tmp_pwd = self.config.get('oVirt', 'TmpPwd')
        wlanwifi = self.config.get('Config', 'cbtn_wlan')

        self.settings.read('/root/.config/spicy/settings')
        rguest = self.settings.get('general', 'resize-guest')
        scal = self.settings.get('general', 'scaling')
        # str2bool function str lower in "true" "t" "1" "yes" "y"
        wlanwifi = bt.str2bool(wlanwifi)
        rguest = bt.str2bool(rguest)
        scal = bt.str2bool(scal)
        name_ent = self.config.get('Userinfo', 'user_name')
        dname_ent = self.config.get('Userinfo', 'user_dpt_name')
        username = self.config.get('oVirt', 'Username')
        passwd = self.config.get('oVirt', 'Password')
        server_ip, port = urlsplit(base_url).netloc.split(':')

        return (base_url, tmp_pwd, wlanwifi,
                rguest, scal, name_ent, dname_ent,
                username, passwd, server_ip, port)

    def save_config(self, save_data):
        (base_url, username, passwd,
         ent_name, ent_dname, reguest, scaling, cbtn_wlan,
         class_url_info) = save_data

        try:
            self.config.set('oVirt', 'BaseUrl', base_url)
        except ConfigParser.NoSectionError:
            self.config.add_section('oVirt')
            self.config.set('oVirt', 'BaseUrl', base_url)
        self.config.set('oVirt', 'username', username)
        self.config.set('oVirt', 'password', passwd)
        self.config.set('Userinfo', 'user_name', ent_name)
        self.config.set('Userinfo', 'user_dpt_name', ent_dname)
        self.config.set('Config', 'cbtn_wlan', cbtn_wlan)
        self.config.set('Class', 'class_url', class_url_info)
        with open('/var/ovirt.conf', 'w') as f:
            self.config.write(f)

        self.settings.read('/root/.config/spicy/settings')
        self.settings.set('general', 'resize-guest', reguest.lower())
        self.settings.set('general', 'scaling', scaling.lower())
        with open('/root/.config/spicy/settings', 'w') as x:
            self.settings.write(x)
        #store the history user and the current user into the config file(/var/users.conf)
        user_list = get_user_list("/var/users.conf")
        if user_list:
            for user in user_list:  # 删除重复的用户
                if username == user["username"]:
                    user_list.remove(user)
        current_user = {"username": username, "password": passwd}
        user_list.insert(0, current_user)  # 将此时登录的用户放在第一个
        with open("/var/users.conf", "w") as user_list_file:
            for user in user_list:
                user_list_file.write(user["username"]+"\t"+user["password"]+"\n")


def get_user_list(path_to_file):
    """从配置中获取之前登录过的用户名和密码"""
    if not os.path.exists(path_to_file):
        os.system("touch users.conf")
    user_list = []
    users = None
    try:
        with open(path_to_file, "r") as user_file:
            users = user_file.readlines()
        for line in users:
            if line.strip():
                user =  line.split("\t")
                user_list.append({"username": user[0].strip(), "password": user[1].strip()})
    except:
        pass
    return user_list
