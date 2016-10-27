#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 ShenCloud Inc.

"""main module"""

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import subprocess
import os
import os.path
import time
import threading
import logging
from subprocess import Popen
from multiprocessing import Process, Pipe
import select
import socket
import argparse
import httplib
import re

import ifconfig
import mainwnd
import loginwindow
import basictools as bt
import settingdialog
import aboutdialog
import checknetdialog
import poweroffdialog
import progressdialog
import passwd
from shencloudlog import init_log, destroy_log
from loginprocess import LoginProcess, get_user_list
from cusdialog import DialogWith1Button, DialogWith2Button
from wlandialog import WLAN_CONN_TIMES, WLAN_CARR, WPA_WAY
import ConfigParser
from action import ActionSender

gobject.threads_init()

CONF_FILE = '/var/ovirt.conf'
CONF_FILE_BAK = '/var/ovirt.conf.bak'
SET_CONF_FILE = '/root/.config/spicy/settings'

IMG_WAITING = 'images/WAITING.png'
IMG_STARTING = 'images/STARTING.png'
IMG_RUNNING = 'images/RUNNING.png'
IMG_STOPPING = 'images/STOPPING.png'
IMG_STOP = 'images/STOPPED.png'
IMG_PAUSED = 'images/PAUSED.png'
IMG_QUESTION = 'images/QUESTIONMARK.png'
IMG_RESTART = 'images/RESTART.png'
WLAN_CMD = """sudo insmod /usr/share/wifi/rtl8188eu.ko
sudo ifconfig wlan0 up
sudo killall wpa_supplicant > /dev/null 2>&1
sudo wpa_supplicant -B -Dwext -iwlan0 -c/etc/wpa_supplicant.conf > /dev/null 2>&1"""
NETIF_RESET_CMD = """sudo ifdown %s
sudo ifup %s"""
NETIF_UP_CMD = "sudo ifconfig %s up"
NETIF_DOWN_CMD = """sudo ifconfig %s 0.0.0.0
sudo ifconfig %s down"""
TEACHER_FLAG = '/etc/sycos/eclass/term_type'

POWEROFF_MSG = '''<shell_cmd>
    <sender>%s</sender>
    <reciever></reciever>
    <cmd>%s</cmd>
</shell_cmd>'''

MIN_BRIGHTNESS_VAL = 27
MAX_BRIGHTNESS_VAL = 255
DEFAULT_UPDATE_INTERVAL = 5
log = logging.getLogger(__name__)

class ShenCloud(object):
    """Initialize the program
    define methods used to reply user opertions
    """
    vms_list = []
    selected_vm = None
    dia_refresh_response = -999
    count = 0
    continue_recv = 0
    task_exit = False
    percent = 0.0
    refresh_start = True
    connect_response = -999
    login_response = -999
    connect_exit = False
    connect_start = True

    def __init__(self, config, settings, admin_allow=True, loglevel=None):
        """
        1. Initialize objects
           OVirtDispatcher() --> dispatcher ovirtsdk, used to login, logout and operate vms.
           MainWindow() --> the main window, initialize main window
           LoginWindow() --> the login window, initialize login window
        2. bind signal and callback function
        3. design virtual machine view format
        4. check autologin
        """

        self.config = config
        self.settings = settings
        self.loglevel = loglevel
        self.wlan_conn_times = 0
        self.__pwdkey = 13  # used to encrypt
        self.__start_timer_id = None
        self.__update_vms_timer_id = None
        self.__wait_connect_timer_id = None
        self.conn_query_timer = None
        # add by zhanglu
        self._on_timer_class = None
        self._on_timer_listen_to_outclass = None
        self._on_timer_waitting_ad = None
        self._on_timer_register_teacher = None
        self._on_time_startall_vms = None
        self.identity_flag = "student"
        self.click_outclass_flag = True

        self.mainwin = None
        self.conn_apply_timer = None
        self.power_key_time = 0
        self.power_key = 0
        self.cur_ip = ''
        self.keep_state_list = []
        self.wait_net_time = 0
        self.net_restart_end = False
        self.current_vm_count = 0
        self.log_refresh = False
        self.start_query = False
        self.conn_apply = False
        self.admin_allow = admin_allow
        self.teacher_flag = False
        self.call_flag = False
        self.connect_flag = False
        self.login_click_num = 0
        self.reconnect_num = 0
        self.is_login = False
        self.soft_version = "SYP_login_version:SYCOS-7.0.2_D4.4-e"

        if os.path.exists("/var/SYP_login_version.info"):
            os.system("rm -rf /var/SYP_login_version.info")
        with open("/var/SYP_login_version.info", 'w') as f:
            f.write(self.soft_version)

        with open('/var/brightness', 'r') as backlight_info:
            backlight_value_info = backlight_info.readlines()
            for info in backlight_value_info:
                backlight_value = info.strip()
            try:
                value = int(backlight_value)
            except Exception:
                value = MAX_BRIGHTNESS_VAL
            if value < MIN_BRIGHTNESS_VAL:
                value = MIN_BRIGHTNESS_VAL
            elif value > MAX_BRIGHTNESS_VAL:
                value = MAX_BRIGHTNESS_VAL
            cmd = 'sudo echo %s > /sys/devices/platform/pwm-backlight.0/backlight/pwm-backlight.0/brightness' % value
            #Popen(cmd, shell=True)

        # 获取屏幕大小情况:1900x1080或者1368x768，这里仅仅获取宽度即可
        width = gtk.gdk.Screen().get_width()
        if width == 1368:
            self.section = "E_Class_Small"
        else:
            self.section = "E_Class"

        self.conn_send, child_conn_recv = Pipe()
        self.conn_recv, child_conn_send = Pipe()
        self.server_conn_send, server_child_conn_recv = Pipe()
        self.server_conn_recv, server_child_conn_send = Pipe()
        self.setting_conn_send, setting_child_conn_recv = Pipe()
        self.setting_conn_recv, setting_child_conn_send = Pipe()
        self.refresh_conn_send, refresh_child_conn_recv = Pipe()
        self.refresh_conn_recv, refresh_child_conn_send = Pipe()
        self.update_vms_send, update_vms_child_recv = Pipe()
        self.update_vms_recv, update_vms_child_send = Pipe()

        # add by zhanglu
        self.rpc_send, child_rpc_recv = Pipe()
        self.rpc_recv, child_rpc_send = Pipe()
        self.rpc_vm_send, child_rpc_vm_recv = Pipe()
        self.rpc_vm_recv, child_rpc_vm_send = Pipe()

        self.login_process = LoginProcess(args=(child_conn_send,
                                                child_conn_recv,
                                                setting_child_conn_send,
                                                setting_child_conn_recv,
                                                refresh_child_conn_send,
                                                refresh_child_conn_recv,
                                                update_vms_child_send,
                                                update_vms_child_recv,
                                                child_rpc_recv,
                                                child_rpc_send,
                                                child_rpc_vm_recv,
                                                child_rpc_vm_send,
                                                self.__pwdkey))

        self.login_process.start()

        self.poller = select.poll()
        self.poller.register(self.conn_recv.fileno(), select.POLLIN)
        self.poller.register(self.refresh_conn_recv.fileno(), select.POLLIN)
        self.poller.register(self.update_vms_recv.fileno(), select.POLLIN)

        self.mutex_send = threading.Lock()
        self.mutex_recv = threading.Lock()
        self.mutex_server_send = threading.Lock()
        self.mutex_server_recv = threading.Lock()
        self.mutex_setting_send = threading.Lock()
        self.mutex_setting_recv = threading.Lock()
        self.mutex_get_vm_send = threading.Lock()
        self.mutex_get_vm_recv = threading.Lock()
        self.mutex_refresh_send = threading.Lock()
        self.mutex_refresh_recv = threading.Lock()
        self.mutex_liststore = threading.Lock()

        # add by zhanglu
        #
        # for waitting ad and register teacher
        #
        self.mutex_rpc_send = threading.Lock()
        self.mutex_rpc_recv = threading.Lock()
        #
        # for start or shutdown all vms
        #
        self.mutex_rpc_vm_send = threading.Lock()
        self.mutex_rpc_vm_recv = threading.Lock()

        self.user = None
        self.pwd = ''

        self.action = ActionSender()
        self.loginwin_Init()

        logoName = self.config.get('Config', 'logo_name')
        self.gladefile = {}
        self.gladefile['progressdialog'] =  logoName + "_progressdialog.glade"
        self.gladefile['aboutdialog'] =  logoName + "_aboutdialog.glade"
        self.gladefile['settingdialog'] =  logoName + "_settingdialog.glade"
        try:
            aut_wlan = self.config.get('Config', 'cbtn_wlan')
        except Exception:
            self.config = ConfigParser.ConfigParser()
            self.config.read(CONF_FILE)
            aut_wlan = self.config.get('Config', 'cbtn_wlan')

        if aut_wlan == 'True':
            gobject.timeout_add(10, self.network_restart_wlan)
        else:
            gobject.timeout_add(10, self.network_restart)

        gobject.timeout_add_seconds(3, self.wait_stu_auto_connect)

    def loginwin_Init(self):
        self.loginwin = loginwindow.LoginWindow(self.__pwdkey, self.conn_send, self.conn_recv, self.mutex_send, self.mutex_recv)
        self.loginwin.show()  # show login window

        # bind signal and callback function
        self.loginwin.btn_login.connect("clicked", self.on_login_clicked)
        self.loginwin.win.connect("key-press-event", self.on_key_press)
        self.loginwin.btn_off.connect("clicked", self.on_poweroff_clicked, "loginwin")
        self.loginwin.btn_manage.connect("clicked", self.on_manage_clicked)

    def wait_stu_auto_connect(self):

        begin_class_file = "/tmp/begin_class"
        if os.path.exists(begin_class_file):
            # with open(begin_class_file, 'r') as f:
            #     content = f.read().strip()

            # if content == "true":
            #     with open(begin_class_file, 'w') as f:
            #         content = f.truncate()

            os.system("rm /tmp/begin_class")
            if self.identity_flag == "teacher":
                log.info("teacher start all vm")
                try:
                    self.mutex_rpc_vm_send.acquire()
                    self.rpc_vm_send.send(('start_all', None))
                finally:
                    self.mutex_rpc_vm_send.release()
                gobject.timeout_add(1000, self.start_all_finish)
            elif not self.is_login:
                if not os.popen("ps aux | grep 'spicy -h' | grep -v grep").read():
                    log.info('auto connecte to vm, ' + str(self.is_login) )
                    self.loginwin.btn_login.emit("clicked")

        return True

    def mainwin_init_teacher(self):
        self.mainwin = mainwnd.MainWindow(self.identity_flag)

#        self.mainwin.btn_off.connect("clicked",
#                                     self.on_poweroff_all_clicked,
#                                     "mainwin")
        self.mainwin.btn_quit.connect("clicked", self.on_quit_clicked)
        self.mainwin.win.connect("key-press-event", self.on_key_press)
        self.mainwin.btn_off.connect("button-press-event", self.poweroff_enter)
        self.mainwin.btn_off.connect("button-release-event", self.poweroff_leave)

    def poweroff_enter(self, widget, data=None):
        """click关机按钮上图片改变"""
        shutdown_img = self.config.get(self.section, 'img_shutdown_enter')
        self.mainwin.pixbuf_shutdown = gtk.gdk.pixbuf_new_from_file(shutdown_img)
        curwidth_small, curheight_small = self.mainwin.btn_off.get_window().get_size()
        self.mainwin.pixbuf_shutdown = self.mainwin.pixbuf_shutdown.scale_simple(curwidth_small, curheight_small, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf( widget.style.bg_gc[gtk.STATE_NORMAL], self.mainwin.pixbuf_shutdown, 0, 0, 0, 0)

        self.on_poweroff_all_clicked("mainwin")

        return True

    def poweroff_leave(self, widget, data=None):
        shutdown_img = self.config.get(self.section, 'img_shutdown_leave')
        self.mainwin.pixbuf_shutdown = gtk.gdk.pixbuf_new_from_file(shutdown_img)
        curwidth_small, curheight_small = self.mainwin.btn_off.get_window().get_size()
        self.mainwin.pixbuf_shutdown = self.mainwin.pixbuf_shutdown.scale_simple(curwidth_small, curheight_small, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.btn_off.style.bg_gc[gtk.STATE_NORMAL], self.mainwin.pixbuf_shutdown, 0, 0, 0, 0)

        return True

    def mainwin_init_admin(self):
        if not self.mainwin:
            self.mainwin = mainwnd.MainWindow(self.identity_flag)
            self.mainwin.btn_quit.connect("clicked", self.on_quit_clicked)
            self.mainwin.btn_off.connect("clicked", self.on_poweroff_clicked, "mainwin")
            self.mainwin.btn_refresh.connect("clicked", self.on_refresh)
            self.mainwin.btn_start.connect("clicked", self.on_start_clicked)
            self.mainwin.btn_stop.connect("clicked", self.on_stop_clicked)
            self.mainwin.btn_about.connect("clicked", self.on_about_clicked)
            self.mainwin.btn_shutdown.connect("clicked", self.on_shutdown_clicked)
            self.mainwin.btn_conn.connect("clicked", self.on_connect_clicked)
            self.mainwin.win.connect("key-press-event", self.on_key_press)
            self.mainwin.treeview_machine.connect("row_activated", self.on_conn_desktop_rapid)


            self.liststore = gtk.ListStore(gtk.gdk.Pixbuf, str, int, str, str, str, str)
            self.modelfilter = self.liststore.filter_new()

            self.vmselect = self.mainwin.treeview_machine.get_selection()
            self.vmselect.connect("changed", self.on_select_changed)
            # design vm view format
            # flag   Name   VCPU   Mem   Disk   Display Interface   Status   USB Policy
            columns = self.mainwin.treeview_machine.get_columns()
            for cn in columns:
                self.mainwin.treeview_machine.remove_column(cn)
            self.mainwin.treeview_machine.columns = [None] * 7
            self.mainwin.treeview_machine.columns[0] = gtk.TreeViewColumn('')
            self.mainwin.treeview_machine.columns[1] = gtk.TreeViewColumn('名称')
            self.mainwin.treeview_machine.columns[2] = gtk.TreeViewColumn('虚拟CPU')
            self.mainwin.treeview_machine.columns[3] = gtk.TreeViewColumn('内存')
            self.mainwin.treeview_machine.columns[4] = gtk.TreeViewColumn('显示接口')
            self.mainwin.treeview_machine.columns[5] = gtk.TreeViewColumn('状态')
            self.mainwin.treeview_machine.columns[6] = gtk.TreeViewColumn('USB策略')
            for cn in xrange(7):
                self.mainwin.treeview_machine.columns[cn].set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            self.mainwin.treeview_machine.columns[0].set_fixed_width(50)
            self.mainwin.treeview_machine.columns[1].set_fixed_width(200)
            self.mainwin.treeview_machine.columns[2].set_fixed_width(120)
            self.mainwin.treeview_machine.columns[3].set_fixed_width(120)
            self.mainwin.treeview_machine.columns[4].set_fixed_width(120)
            self.mainwin.treeview_machine.columns[5].set_fixed_width(120)
            self.mainwin.treeview_machine.columns[6].set_fixed_width(120)
            self.mainwin.treeview_machine.set_model(self.modelfilter)
            for n in xrange(7):
                self.mainwin.treeview_machine.append_column(self.mainwin.treeview_machine.columns[n])
                if n == 0:
                    self.mainwin.treeview_machine.columns[n].cell = gtk.CellRendererPixbuf()
                    self.mainwin.treeview_machine.columns[n].pack_start(self.mainwin.treeview_machine.columns[n].cell, True)
                    self.mainwin.treeview_machine.columns[n].set_attributes(self.mainwin.treeview_machine.columns[n].cell,
                                                                            pixbuf=n)
                else:
                    self.mainwin.treeview_machine.columns[n].cell = gtk.CellRendererText()
                    self.mainwin.treeview_machine.columns[n].pack_start(self.mainwin.treeview_machine.columns[n].cell, True)
                    self.mainwin.treeview_machine.columns[n].set_attributes(self.mainwin.treeview_machine.columns[n].cell, text=n)

            self.vm_state = {}
            self.vm_state['waiting'] = {'image': gtk.gdk.pixbuf_new_from_file(IMG_WAITING), 'descp': '等待启动'}
            self.vm_state['starting'] = {'image': gtk.gdk.pixbuf_new_from_file(IMG_STARTING), 'descp': '正在启动'}
            self.vm_state['running'] = {'image': gtk.gdk.pixbuf_new_from_file(IMG_RUNNING), 'descp': '运行'}
            self.vm_state['stopping'] = {'image': gtk.gdk.pixbuf_new_from_file(IMG_STOPPING), 'descp': '正在关闭'}
            self.vm_state['stop'] = {'image': gtk.gdk.pixbuf_new_from_file(IMG_STOP), 'descp': '关闭'}
            self.vm_state['paused'] = {'image': gtk.gdk.pixbuf_new_from_file(IMG_PAUSED), 'descp': '休眠'}
            self.vm_state['question'] = {'image': gtk.gdk.pixbuf_new_from_file(IMG_QUESTION), 'descp': '故障'}
            self.vm_state['restart'] = {'image': gtk.gdk.pixbuf_new_from_file(IMG_RESTART), 'descp': '正在重启'}
            self.state_map = {'wait_for_launch':'waiting', 'powering_up':'starting', 'up': 'running',
                               'powering_down': 'stopping', 'down': 'stop', 'reboot_in_progress': 'restart',
                               'suspended': 'paused', 'saving_state': 'paused', 'restoring_state': 'paused'}

        self.mainwin.lbl_user.set_text(self.user)
        self.mainwin.win.show()



    def check_eth(self, widget=None):
        curif = ''

        for iter_ in ifconfig.list_ifs():
            curif = ifconfig.find_if_by_name(iter_)
        return curif.name

    def check_net_up(self, widget=None):
        eth = self.check_eth()
        log.info(eth)
        with open('/etc/network/interfaces', 'r') as net_file:
            net_info = net_file.readlines()
            for line in net_info:
                if eth in line:
                    break
                    return False
            else:
                return True

    def network_restart_wlan(self, widget=None):
        subprocess.Popen(WLAN_CMD, shell=True)
        self.network_dialog = checknetdialog.CheckNet()
        self.network_dialog.lbl_msg.set_text("正在启动无线网络...请稍候")
        self.network_dialog.btn_cancel = self.network_dialog.dialog.add_button("关闭", gtk.RESPONSE_CANCEL)
        self.network_dialog.btn_cancel.connect("clicked", self.on_network_distroy)
        gobject.timeout_add_seconds(3, self.wlan_conn_msg)
        return False

    def wlan_conn_msg(self):
        eth = self.check_eth()
        self.wlan_conn_times += 1
        subprocess.call(NETIF_DOWN_CMD % (eth, eth), shell=True)
        subprocess.call(NETIF_RESET_CMD % ('wlan0', 'wlan0'), shell=True)
        subprocess.Popen("sudo dhclient wlan0 > /dev/null 2>&1", shell=True)
        try:
            val = subprocess.check_output(WLAN_CARR, shell=True)
        except Exception:
            return True
        li = val.strip('\n').strip()
        if li == '1':
            self.base_url = self.config.get('oVirt', 'BaseUrl')
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
            self.network_dialog.lbl_msg.set_text("无线连接成功！")
            self.wlan_conn_times = 0
            gobject.timeout_add(100, self.network_get_ip, True)
            gobject.timeout_add_seconds(3, self.set_network_distroy)
            return False
        elif self.wlan_conn_times >= WLAN_CONN_TIMES:
            self.network_dialog.lbl_msg.set_text("无线连接失败, 请检查密码是否正确！")
            return False
        return True

    def set_network_distroy(self):
        self.network_dialog.btn_cancel.emit("clicked")

    def on_network_distroy(self, widget):
        self.network_dialog.dialog.destroy()

    def network_restart(self, widget=None):
        gobject.timeout_add(1, self.check_net_up)
        self.net_process = None
        self.wait_net_time = 0
        self.carry_try_times = 0
        self.network_dialog = checknetdialog.CheckNet()
        self.network_dialog.lbl_msg.set_text("正在启动网络...请稍候")
        self.network_dialog.btn_cancel = self.network_dialog.dialog.add_button("关闭", gtk.RESPONSE_CANCEL)
        gobject.timeout_add(1, self.network_run)
        gobject.timeout_add(1000, self.network_carry)
        return False

    def network_run(self):
        self.network_dialog.run()
        if self.net_process:
            self.net_process.terminate()
        #self.checkautologin()  # check autologin status

    def network_carry(self):
        eth = self.check_eth()
        self.net_restart_end = False
        self.wait_net_time = 0
        self.carry_try_times += 1
        try:
            with open('/sys/class/net/%s/carrier' % (eth), 'r') as carrier_file:
                carrier_info = carrier_file.read()
                retcode = carrier_info.strip()
        except:
            os.system("sudo ifconfig %s up" % eth)
            return True
        if retcode == '1':
            gobject.timeout_add(100, self.network_get_ip)
            self.net_process = Process(target=self.network_process, args=())
            self.net_process.start()
            self.net_process.join()
        else:
            if self.carry_try_times <= 10:
                return True
            self.network_dialog.lbl_msg.set_text("未检测到有网络电缆插入,请连接好网络电缆后点击继续")
            self.network_dialog.btn_ok = self.network_dialog.dialog.add_button("继续", gtk.RESPONSE_OK)
            self.network_dialog.btn_ok.connect("clicked", self.network_restart)

        return False

    def waitting_ad_finish(self):
        rpc_poller = select.poll()
        rpc_poller.register(self.rpc_recv.fileno(), select.POLLIN)
        events = rpc_poller.poll(10)
        for fd, event in events:
            if fd == self.rpc_recv.fileno() and event & select.POLLIN:
                try:
                    self.mutex_rpc_recv.acquire()
                    msg_type, msg_data = self.rpc_recv.recv()
                finally:
                    self.mutex_rpc_recv.release()
                if msg_type != "waitting_ad" and not msg_data:
                    log.error("call rpc waitting_ad failed")
                    self.network_distroy()
                    return True
                else:
                    self.network_distroy()
                    # if there is autologin, put it here
                    self.checkautologin()  # check autologin status
            return False
        return True

    def waitting_server_start(self):
        conn_poller = select.poll()
        conn_poller.register(self.conn_recv.fileno(), select.POLLIN)
        events = conn_poller.poll(10)
        for fd, event in events:
            if fd == self.conn_recv.fileno() and event & select.POLLIN:
                try:
                    self.mutex_recv.acquire()
                    msg_type, msg_data = self.conn_recv.recv()
                finally:
                    self.mutex_recv.release()

                if msg_type != "waitting_server_up" and not msg_data:
                    log.error("waitting server up failed")
                    self.network_distroy()
                    return True
                else:
                    self.network_distroy()
                    # if there is autologin, put it here
                    self.checkautologin()  # check autologin status
            return False
        return True

    def network_get_ip(self, wlan_on=False):
        self.wait_net_time += 1
        curif = ''

        for iter_ in ifconfig.list_ifs():
            curif = ifconfig.find_if_by_name(iter_)
            if (wlan_on and (not curif.name.startswith('wlan'))) \
               or ((not wlan_on) and curif.name.startswith('wlan')) \
               or curif.name == 'lo':
                continue
            if curif.is_up():
                self.cur_ip = curif.get_ip()
                if self.cur_ip:
                    break
                #time.sleep(2)
        if self.wait_net_time <= 40:
            return True
        if self.wait_net_time <= 800:
            if self.cur_ip:
                self.network_dialog.lbl_msg.set_text("网络启动成功!")
                _, _, gate_way = bt.get_static_ipinfo_by_name(curif)
                if gate_way:
                    subprocess.Popen('sudo route add defalut gw %s %s' % (gate_way, curif), shell=True)
                self.network_distroy()

                def waitting_dialog(text):
                    self.network_dialog = checknetdialog.CheckNet()
                    self.network_dialog.lbl_msg.set_text(text)
                    #self.network_dialog.btn_cancel = self.network_dialog.dialog.add_button("关闭", gtk.RESPONSE_CANCEL)
                    self.network_dialog_run()

                try:
                    ldap_flag = bt.str2bool(self.config.get('oVirt', 'ldap', "True"))
                except:
                    ldap_flag = True
                if ldap_flag:
                    ret = ifconfig.ping_server()
                    if not ret:
                        try:
                            self.mutex_send.acquire()
                            self.conn_send.send(('waitting_server_up', None))
                        finally:
                            self.mutex_send.release()
                        gobject.timeout_add(1, waitting_dialog, "等待服务器启动完成...")
                        gobject.timeout_add(3000, self.waitting_server_start)
                    else:
                        self.checkautologin()  # check autologin status
                else:
                    gobject.timeout_add(1, waitting_dialog, "等待域控启动完成...")
                    try:
                        self.mutex_rpc_send.acquire()
                        self.rpc_send.send(('waitting_ad', None))
                    finally:
                        self.mutex_rpc_send.release()
                    gobject.timeout_add(1000, self.waitting_ad_finish)
                self.net_restart_end = True
                self.wait_net_time = 0
                return False
            else:
                return True
        else:
            self.network_dialog.lbl_msg.set_text("网络启动超时,请打开设置页面手动配置网络!")
            #self.network_dialog.btn_ok = self.network_dialog.dialog.add_button("关闭", gtk.RESPONSE_OK)
            self.wait_net_time = 0
            return False

    def network_distroy(self):
        self.network_dialog.response(gtk.RESPONSE_CANCEL)
        self.network_dialog = None

    def network_process(self):
        eth = self.check_eth()
        net_info = ''
        with open('/etc/network/interfaces', 'r') as net_file:
            net_info = net_file.read()
            if 'dhcp' in net_info:
                os.system("sudo dhclient %s & > /dev/null 2>&1" % (eth))
            else:
                os.system("sudo ifconfig %s up" % (eth))


    def user_login_unlock(self, stat):
        """Lock or unlock login input

            stat    True if unlock the login input
                    False if lock the login input
        """
        if self.loginwin is not None:
            self.loginwin.on_user_unlock(stat)

    def network_dialog_run(self):
        self.network_dialog.run()

    def is_wlan_on(self):
        self.config.read('/var/ovirt.conf')
        aut_wlan = self.config.get('Config', 'cbtn_wlan')
        if aut_wlan == "True":
            wlan_on = True
        else:
            wlan_on = False

        return wlan_on

    def on_login_clicked(self, widget, data=None):
        """login main window"""
        self.login_click_num += 1
        wlan_on = self.is_wlan_on()
        cur_ip = ''
        for if_name in ifconfig.list_ifs():
            if wlan_on and not if_name.startswith('wlan'):
                continue
            curif = ifconfig.find_if_by_name(if_name)
            if curif.is_up():
                cur_ip = curif.get_ip()
            else:
                continue
            if not cur_ip:
                net_info = ''
                with open('/etc/network/interfaces', 'r') as net_file:
                    net_infos = net_file.readlines()
                    for net_info in net_infos:
                        if 'dhcp' in net_info and if_name in net_info:
                            Popen("sudo kill `ps aux | grep dhclient | grep %s | grep -v grep | awk '{print $2}'` > /dev/null 2>&1" % if_name,
                                  shell=True)
                            Popen("sudo route del default", shell=True)
                            Popen("sudo ifconfig %s 0.0.0.0" % if_name, shell=True)
                            Popen("sudo dhclient %s > /dev/null 2>&1" % if_name, shell=True)
                            break
                        elif 'static' in net_info and if_name in net_info:
                            net_ip = net_mask = gate_way = ''
                        else:
                            continue

                        line = net_info
                        if 'address' in line:
                            net_ip = line.strip()[7:].strip().strip('\n')
                        elif 'netmask' in line:
                            net_mask = line.strip()[7:].strip().strip('\n')
                        elif 'gateway' in line:
                            gate_way = line.strip()[7:].strip().strip('\n')
                        if net_ip and net_mask and gate_way:
                            Popen("sudo kill `ps aux | grep dhclient | grep %s | grep -v grep | awk '{print $2}'` > /dev/null 2>&1" % if_name,
                                  shell=True)
                            Popen("sudo route del default", shell=True)
                            cmd = 'sudo ifconfig %s %s netmask %s' % (if_name, net_ip, net_mask)
                            Popen("sudo ifconfig %s up" % if_name, shell=True)
                            Popen(cmd, shell=True)
                            Popen("sudo route add default gw %s %s" % (gate_way, if_name), shell=True)
                            net_ip = net_mask = gate_way = ''
                            break
            break

        if not self.__validcheck():
            # add to solve bug:　自动登录时，配置文件中未读取到用户名和密码，手动输入后，点击"登录"无反应。
            self.login_click_num = 0
            return False
        self.is_login = True
        self.loginwin.lbl_warn.set_text('')
        user = self.loginwin.entbuf_user.child.get_text().strip()
        pwd = self.loginwin.entbuf_pwd.get_text().strip()
        self.user = user
        self.pwd = pwd
        ShenCloud.login_response = -999
        with self.mutex_send:
            self.conn_send.send(('login', (user, pwd)))

        ShenCloud.vms_list = []
        if self.login_click_num == 2:
            pass
        else:
            ShenCloud.percent = 0.05
            self.__login_dia_timer_id = gobject.timeout_add(1, self.login_dia_run)
            self.__login_wait_timer_id = gobject.timeout_add(1000, self.login_mainwnd, widget)

    def login_dia_run(self):

        self.dia_login = progressdialog.Refresh(self.gladefile['progressdialog'])
        self.dia_login.btn_cancel = self.dia_login.dialog.add_button("放弃", gtk.RESPONSE_CANCEL)
        self.dia_login.lbl_vm.set_text('正在登录云系统...')
        ShenCloud.login_response = self.dia_login.run()
        if self.identity_flag == "student":
            self.user = None
        self.login_click_num = 0
        if self.__login_wait_timer_id:
            gobject.source_remove(self.__login_wait_timer_id)
            self.__login_wait_timer_id = None
        self.dia_login.destroy()
        self.dia_login = None
        with self.mutex_send:
            self.conn_send.send(('login_terminate', ''))
        #end

        return False

    def start_all_finish(self):
        self.start_all_flag = False
        rpc_poller = select.poll()
        rpc_poller.register(self.rpc_vm_recv.fileno(), select.POLLIN)
        events = rpc_poller.poll(10)
        for fd, event in events:
            if fd == self.rpc_vm_recv.fileno() and event & select.POLLIN:
                try:
                    self.mutex_rpc_vm_recv.acquire()
                    msg_type, msg_data = self.rpc_vm_recv.recv()
                finally:
                    self.mutex_rpc_vm_recv.release()
                if msg_type == "start_all":
                    log.info("start all vms success!")
                self.start_all_flag = True
                return False

        return True

    def finish_class_control(self, msg):
        def show_dialog(text):
            self.network_dialog1 = checknetdialog.CheckNet()
            self.network_dialog1.lbl_msg.set_text(text)
            self.network_dialog1.btn_cancel = self.network_dialog1.dialog.add_button("关闭", gtk.RESPONSE_CANCEL)
            if self.dia_connect:
                self.dia_connect.destroy()
            self.network_dialog1.run()
            return False

        if msg == "restart_vm" or msg == "shutdown_vm_term":
            try:
                self.mutex_rpc_vm_send.acquire()
                self.rpc_vm_send.send((msg, None))
                log.debug("finish_class rpc send 'shutdown_vm'")
            finally:
                self.mutex_rpc_vm_send.release()
        elif msg == "shutdown_server":
            log.debug("finish_class close server")
            gobject.timeout_add(1000, self.close_server1)
            gobject.timeout_add(1, show_dialog, "正在关闭服务器...请稍候")
            gobject.timeout_add(1000, self.waitting_server_down)

        if msg == "shutdown_vm_term" or msg == "shutdown_server":
            try:
                self.mutex_send.acquire()
                self.conn_send.send(('poweroff_stu', None))
            finally:
                self.mutex_send.release()
            log.debug("finish_class shutdown student's terminal")


    def listen_to_outclass(self):
        finish_class_file = "/tmp/finish_class"
        if os.path.exists(finish_class_file):
            with open(finish_class_file, 'r') as f:
                try:
                    _, vm_action = f.read().strip().split(',')
                except:
                    return True

            with open(finish_class_file, 'w') as f:
                f.truncate()

            if vm_action == '0':
                msg = "restart_vm"
            elif vm_action =='1':
                msg = "shutdown_vm_term"
            elif vm_action =='2':
                msg = "shutdown_server"
            else:
                log.info("Read from 'finish_class' invalid para '%s'" % vm_action)
                msg = ""

            self.finish_class_control(msg)

        return True

    def login_mainwnd(self, widget):

        self.dia_login.progressbar.set_fraction(ShenCloud.percent)
        ShenCloud.percent += 0.05
        if ShenCloud.percent >= 1:
            ShenCloud.percent = 0.0

        events = self.poller.poll(10)

        for fd, event in events:
            if fd == self.conn_recv.fileno() and event & select.POLLIN:
                try:
                    self.mutex_recv.acquire()
                    msg_type, msg_data = self.conn_recv.recv()
                finally:
                    self.mutex_recv.release()

                if msg_type == 'login':

                    # If login successfully, lock the login input
                    self.user_login_unlock(False)
                    ret, base_url, info, vmList = msg_data
                    if self.user.startswith(("tec-", "tec_", "teacher")):
                        self.identity_flag = "teacher"
                    elif self.user.startswith("admin"):
                        self.identity_flag = "admin"
                    else:
                        self.identity_flag = "student"
                    if ret:
                        log.info("User login success. username=%s, dest_url=%s",
                                 self.user, base_url)
                        self.dia_login.btn_cancel.emit("clicked")
                        # 三种身份登陆后的界面
                        if self.identity_flag == "student":
                            self.loginwin.btn_manage.hide()
                            stream_value = 2
                            try:
                                self.settings.set('server', 'stream', stream_value)
                                with open('/root/.config/spicy/settings', 'w') as x:
                                    self.settings.write(x)
                            except:
                                with open('/root/.config/spicy/settings', 'a') as fp:
                                    fp.write('\n[server]\nstream = 2')
                            # 直接连接虚拟机

                            self.connect_vm()

                        elif self.identity_flag == "admin":
                            self.loginwin.btn_manage.hide()
                            if len(vmList) == 1:
                                self.connect_vm(vmList[0])
                            else:
                                self.mainwin_init_admin()
                                self.loginwin.win.hide()
                                self.log_refresh = True
                                self.mainwin.btn_refresh.emit('clicked')
                                self.update_vms_send.send(('update_vms', DEFAULT_UPDATE_INTERVAL))
                                self.__update_vms_timer_id = gobject.timeout_add(200, self.__on_timer_update_vms)
                        elif self.identity_flag == "teacher":
                            self.loginwin.btn_manage.hide()
                            stream_value = 3
                            try:
                                self.settings.set('server', 'stream', stream_value)
                                with open('/root/.config/spicy/settings', 'w') as x:
                                    self.settings.write(x)
                            except:
                                with open('/root/.config/spicy/settings', 'a') as fp:
                                    fp.write('\n[server]\nstream = 3')
                            # 教师端登陆成功后, 向服务器发送开启
                            # 虚拟机命令并监听上下课事件
                            if not self._on_timer_listen_to_outclass:
                                self._on_timer_listen_to_outclass = gobject.timeout_add(3000, self.listen_to_outclass)
                            self.connect_vm()

                        self.log_refresh = True
                        self.set_action_info("user_login")

                        if self.loginwin.cbtn_storepwd.get_active():
                            passwd = self.pwd
                        else:
                            passwd = ''
                            self.loginwin.entbuf_pwd.set_text(passwd)

                        try:
                            self.mutex_send.acquire()
                            self.conn_send.send(('storepwd', (self.user, passwd)))
                        finally:
                            self.mutex_send.release()

                        try:
                            action_time = time.strftime('%Y-%m-%d %H:%M:%S')
                            self.mutex_server_send.acquire()
                            action_time = time.strftime('%Y-%m-%d %H:%M:%S')
                            self.server_conn_send.send(('user_login', (self.user, '-', action_time)))
                        finally:
                            self.mutex_server_send.release()
                        return False
                    else:
                        self.dia_login.response(gtk.RESPONSE_CANCEL)
                        log.error("User login failed! username=%s, dest_url=%s. reason: %s", self.user, base_url, info)
                        gobject.timeout_add(100, self.login_error, info)
                        self.user = None
                        return False
                    self.login_click_num = 0
                else:
                    return True

        else:
            return True
            # TODO: connect timeout


    def login_error(self, info):
        errordlg = DialogWith1Button(btn1_label='确定', btn1_ret='OK')
        errordlg.set_label_text(info)
        self.config.read('/var/ovirt.conf')
        errordlg.run()
        return False

    def timeout_add(self, mseconds, callback, arg=None):
        #p = Process(target=self.start_timer, args=(mseconds,callback,arg))
        #p.start()
        gobject.idle_add(self.start_timer, mseconds, callback, arg)
        return False

    def start_timer(self, mseconds, callback, arg=None):

        self.__start_timer_id = gobject.timeout_add(mseconds, callback, arg)

    def __on_timer_update_vms(self):
        """refresh virtual-machine view and resource view eyery 5 seconds"""

        events = self.poller.poll(10)
        for fd, event in events:
            if fd == self.update_vms_recv.fileno() and event & select.POLLIN:
                msg_type, msg_data = self.update_vms_recv.recv()
                if msg_type == 'update_vms':
                    if not msg_data:
                        return True
                    vms_list_old = ShenCloud.vms_list
                    ShenCloud.vms_list = msg_data[0]
                    with self.mutex_liststore:
                        self.vms_update(ShenCloud.vms_list ,vms_list_old)
                else:
                    log.error("__on_timer_update_vms %s", msg_type)

        return True

    def get_vm(self, from_list, vm_id):
        vm_row = 0
        for vm in from_list:
            if vm['id'] == vm_id:
                return vm, vm_row
            vm_row += 1
        return None, vm_row

    def find_keep_state(self, vm_name):
        for vm in self.keep_state_list:
            if vm_name in vm:
                return vm
        return None

    def vms_update(self, vms_list_new, vms_list_old):
        vms_changed = False
        for vm_new in vms_list_new:

            vm_id = vm_new['id']
            vm_state = vm_new['state']
            vm_name = vm_new['name']
            vm_cpu = int(vm_new['cpu'])
            vm_mem = '%.1f GB' % (int(vm_new['mem'])/1024.0)
            protocal = vm_new['disp']
            usb_policy = '%s' % '允许' if vm_new['usb'] else '不允许'
            vm_old, vm_row = self.get_vm(vms_list_old, vm_id)

            keep_state = self.find_keep_state(vm_name)
            if keep_state:
                if keep_state[1] == 'up':
                    if vm_state == 'down':
                        continue
                    else:
                        self.keep_state_list.remove(keep_state)
                elif keep_state[1] == 'down':
                    if vm_state == 'up':
                        continue
                    else:
                        self.keep_state_list.remove(keep_state)

            try:
                key = self.state_map[vm_state]
                pixbuf = self.vm_state[key]['image']
                vm_state = self.vm_state[key]['descp']
            except Exception as e:
                log.error("State error: %s" % e)
                pixbuf = self.vm_state['question']['image']
                vm_state = self.vm_state['question']['descp']

            if vm_old:
                if vm_old['state'] == vm_new['state']:
                    continue
                else:
                    vms_changed = True
                    try:
                        select_iter = self.liststore.get_iter(vm_row)
                        self.liststore.set(select_iter, 0, pixbuf)
                        self.liststore.set(select_iter, 5, vm_state)
                    except:
                        log.error('vms_update modify liststore.get_iter error')
                        continue
                    self.on_select_changed(self.vmselect)
            else:
                try:
                    self.liststore.append([pixbuf, vm_name, vm_cpu, vm_mem, protocal, vm_state, usb_policy])
                except:
                    log.error('vm_state liststore insert error')
                    continue
        if vms_changed:
            self.on_refresh_res()

    def refresh_show(self, vms_list):

        self.liststore.clear()
        for vm in vms_list:

            vm_state = vm['state']
            vm_name = vm['name']
            vm_cpu = int(vm['cpu'])
            vm_mem = '%.1f GB' % (int(vm['mem'])/1024.0)
            protocal = vm['disp']
            usb_policy = '%s' % '允许' if vm['usb'] else '不允许'

            try:
                key = self.state_map[vm_state]
                pixbuf = self.vm_state[key]['image']
                vm_state = self.vm_state[key]['descp']
            except Exception as e:
                log.error("State error: %s" % e)
                pixbuf = self.vm_state['question']['image']
                vm_state = self.vm_state['question']['descp']

            self.liststore.append([pixbuf, vm_name, vm_cpu, vm_mem, protocal, vm_state, usb_policy])
            log.info("vm: %s, cpu: %d, mem: %s, protocal: %s, state: %s, usb policy: %s",
                     vm_name, vm_cpu, vm_mem, protocal, vm_state, usb_policy)

        self.on_refresh_res()
        return False

    def __on_timer_dialog_run(self):
        """run dialog_refresh"""

        ShenCloud.dia_refresh_response = self.dia_refresh.run()

        self.mainwin.win.set_focus(self.mainwin.treeview_machine)
        ShenCloud.task_exit = True

        with self.mutex_refresh_send:
            self.refresh_conn_send.send(('stop_refresh', None))

        if self.__progress_move_timer_id:
            gobject.source_remove(self.__progress_move_timer_id)
            self.__progress_move_timer_id = None

        if self.log_refresh:
            auto_login = str(self.loginwin.cbtn_autologin.get_active())
            storepwd_login = str(self.loginwin.cbtn_storepwd.get_active())
            self.config.read('/var/ovirt.conf')
            self.config.set('oVirt', 'autologin', auto_login)
            self.config.set('oVirt', 'storepwd', storepwd_login)
            with open('/var/ovirt.conf', 'w') as d:
                self.config.write(d)

            self.log_refresh = False
        return False

    def on_refresh(self, widget, data=None):
        """refresh virtual-machine view and resource view"""

        log.info("user: %s refresh the virsual machine list info.", self.user)
        ShenCloud.progbar_new_value = 0.05

        ShenCloud.count = 1
        ShenCloud.dia_refresh_response = -999
        ShenCloud.percent = 0.0
        ShenCloud.task_exit = False
        ShenCloud.refresh_start = True
        self.current_vm_count = 0

        self.mainwin.btn_start.set_sensitive(False)
        self.mainwin.btn_stop.set_sensitive(False)
        self.mainwin.btn_shutdown.set_sensitive(False)
        self.mainwin.btn_conn.set_sensitive(False)

        self.dia_refresh = progressdialog.Refresh(self.gladefile['progressdialog'])
        self.dia_refresh.btn_cancel = self.dia_refresh.dialog.add_button("放弃", gtk.RESPONSE_CANCEL)
        self.__dialog_refresh_timer_id = gobject.timeout_add(1, self.__on_timer_dialog_run)

        self.__progress_move_timer_id = gobject.timeout_add(100,
                                                            self.__on_timer_progress_move,
                                                            widget)

    def on_refresh_res(self):
        """refresh resource view"""

        allvms = len(ShenCloud.vms_list)
        allvcpus = 0
        allvmem = 0
        curvms = 0
        curvcpus = 0
        curvmem = 0
        for vm in xrange(0, allvms):
            allvcpus += ShenCloud.vms_list[vm]['cpu']
            allvmem += ShenCloud.vms_list[vm]['mem']
            if ShenCloud.vms_list[vm]['state'] != 'down':
                curvms += 1
                curvcpus += ShenCloud.vms_list[vm]['cpu']
                curvmem += ShenCloud.vms_list[vm]['mem']
        curvmem = '%.1f' % (curvmem/1024.0)
        allvmem = '%.1f' % (allvmem/1024.0)
        self.mainwin.lbl_sum_vm.set_text(str(allvms))
        self.mainwin.lbl_curr_vm.set_text(str(curvms))
        self.mainwin.lbl_sum_vcpu.set_text(str(allvcpus))
        self.mainwin.lbl_curr_vcpu.set_text(str(curvcpus))
        self.mainwin.lbl_sum_vmem.set_text(str(allvmem) + 'GB')
        self.mainwin.lbl_curr_vmem.set_text(str(curvmem) + 'GB')
        if allvms:
            percent = float(curvms) / allvms
            self.mainwin.Progbar_vms.set_fraction(percent)
        else:
            return
        if allvcpus:
            percent = float(curvcpus) / allvcpus
            self.mainwin.Progbar_vcpu.set_fraction(percent)
        else:
            return
        if allvmem:
            percent = float(curvmem) / float(allvmem)
            self.mainwin.Progbar_vmem.set_fraction(percent)
        else:
            return

    def __on_timer_progress_move(self, widget):

        if ShenCloud.refresh_start:
            with self.mutex_refresh_send:
                self.refresh_conn_send.send(('refresh', (self.user)))
            ShenCloud.refresh_start = False
        self.dia_refresh.progressbar.set_fraction(ShenCloud.percent)
        ShenCloud.percent += 0.01
        if ShenCloud.percent >= 1:
            ShenCloud.percent = 0.0
        if ShenCloud.task_exit:
            return False
        events = self.poller.poll(10)
        for fd, event in events:
            if fd == self.refresh_conn_recv.fileno() and event & select.POLLIN:
                with self.mutex_refresh_recv:
                    msg_type, msg_data = self.refresh_conn_recv.recv()
                if msg_type == 'refresh':
                    self.dia_refresh.response(gtk.RESPONSE_CANCEL)
                    if not msg_data:
                        self.dia_refresh.lbl_vm.set_text('获取当前用户的虚拟机信息失败！')
                        return False
                    log.info('refresh vms successful!')
                    self.dia_refresh.lbl_vm.set_text('已获取当前用户的虚拟机信息...')

                    ShenCloud.vms_list = msg_data[0]

                    with self.mutex_liststore:
                        self.refresh_show(ShenCloud.vms_list)

                    return False
                else:
                    log.error("msg type is not 'refresh', it is '%s'", msg_type)
                    return False
            else:
                log.error("fd and event are not match when refresh.")
                return False

        return True

    def waiting_state(self, vm_num, vm_name, state):

        for st in self.keep_state_list:
            if vm_name in st:
                return
        self.keep_state_list.append((vm_name, state))

        if state == 'up':
            vm_state = '等待启动'
        else:
            vm_state = '等待关闭'
        pixbuf = self.vm_state['waiting']['image']
        with self.mutex_liststore:
            try:
                select_iter = self.liststore.get_iter(vm_num)
            except:
                log.error('__on_timer_vm_state liststore.get_iter error')
                return True
            self.liststore.set(select_iter, 0, pixbuf)
            self.liststore.set(select_iter, 5, vm_state)

    def on_outclass(self):
        """ out of class. It's shutdown students's computer"""
        self.click_outclass_flag = False

    def waitting_connect_vm(self):
        time.sleep(1)
        self.network_dialog.dialog.destroy()
        # 是否连接
        #dialog = DialogWith2Button()
        #dialog.set_label_text("是否连接桌面？")
        #ret = dialog.run()
        #if ret:
        # 连接桌面
        self.connect_vm()
        return False

    def on_timer_in_class(self):
        """监听上下课动作
        教师端成功登陆后，点击上下课就会修改上下课标识
        """
        self.config.read("/var/ovirt.conf")

        def resume_class(class_flag):
            # 还原上下课标识位(将标识位改为False)
            self.config.read("/var/ovirt.conf")
            self.config.set('Class', class_flag, "False")
            with open('/var/ovirt.conf', 'w') as f:
                self.config.write(f)

        # 获取上下课标识
        try:
            inclass = bt.str2bool(self.config.get('Class', 'shangke'))
        except:
            resume_class("shangke")
            inclass = bt.str2bool(self.config.get('Class', 'shangke'))
        try:
            outclass = bt.str2bool(self.config.get('Class', 'xiake'))
        except:
            resume_class("xiake")
            outclass = bt.str2bool(self.config.get('Class', 'xiake'))

        if inclass and not outclass:  # 点击了上课
            resume_class("shangke")
            def start_dialog():
                self.network_dialog = checknetdialog.CheckNet()
                self.network_dialog.lbl_msg.set_text("正在启动虚拟机...请稍候")
                self.network_dialog.btn_cancel = self.network_dialog.dialog.add_button("关闭", gtk.RESPONSE_CANCEL)
                #gobject.timeout_add(1, self.network_dialog.run)
                self.network_dialog.run()

                return False
            #if not self.click_outclass_flag:
            try:
                self.mutex_rpc_vm_send.acquire()
                self.rpc_vm_send.send(('start_all', None))
            finally:
                self.mutex_rpc_vm_send.release()

            self.mutex_send.acquire()
            try:
                self.conn_send.send(('stu_auto_connect', None))
                log.info('teacher send auto connect vm to server')
            finally:
                self.mutex_send.release()

            gobject.timeout_add(1, start_dialog)
            gobject.timeout_add(1000, self.start_all_finish)
            gobject.timeout_add(2000, self.waitting_connect_vm)
            #else:
            #    start_dialog = checknetdialog.CheckNet()
            #    start_dialog.lbl_msg.set_text("正在关闭学生端虚拟机...请稍候")
            #    start_dialog.btn_cancel = start_dialog.dialog.add_button("关闭", gtk.RESPONSE_CANCEL)
            #    start_dialog.run()

        elif outclass and not inclass:  # 点击了下课
            # In 60s, teacher can't click inclass button and start all vms
            #gobject.timeout_add_seconds(60, self.on_outclass)
            resume_class("xiake")
            self.outclass_flag = None
            # 是否下课
            def outof_class():
                self.out_class_dialog = DialogWith2Button()
                self.out_class_dialog.set_label_text("确定下课？")
                self.outclass_flag = self.out_class_dialog.run()

                return False

            def class_over():
                if self.outclass_flag:  # 确认下课
                    #gobject.timeout_add(100, self.terminate_demon)
                    try:
                        self.mutex_send.acquire()
                        self.conn_send.send(('terminate_demon', None))
                    finally:
                        self.mutex_send.release()

                    try:
                        self.mutex_rpc_vm_send.acquire()
                        self.rpc_vm_send.send(("shutdown_all", None))
                    finally:
                        self.mutex_rpc_vm_send.release()
                    #gobject.timeout_add(1000, self.shutdown_all_finish)

                    return False

                return True

            gobject.timeout_add(1, outof_class)
            gobject.timeout_add(1, class_over)

        else:
            resume_class("shangke")
            resume_class("xiake")

        return True

    def shutdown_all_finish(self):
        rpc_poller = select.poll()
        rpc_poller.register(self.rpc_vm_recv.fileno(), select.POLLIN)
        events = rpc_poller.poll(10)
        for fd, event in events:
            if fd == self.rpc_vm_recv.fileno() and event & select.POLLIN:
                try:
                    self.mutex_rpc_vm_recv.acquire()
                    msg_type, msg_data = self.rpc_vm_recv.recv()
                finally:
                    self.mutex_rpc_vm_recv.release()
                if msg_type == "shutdown_all":
                     log.info("shutdown all vms success!")
                return False
        return True

    def on_start_clicked(self, widget, data=None):
        """start virtual machine"""

        if not ShenCloud.selected_vm:
            log.error('start vm None')
        else:
            vmDict = ShenCloud.selected_vm['content']
            vmIndex = ShenCloud.selected_vm['index']

        if not cmp(vmDict['state'], 'down'):
            self.waiting_state(vmIndex, vmDict['name'], 'up')

        with self.mutex_send:
            self.conn_send.send(('start', (vmDict['name'], vmDict['id'],)))

    def on_stop_clicked(self, widget, data=None):
        """stop virtual machine"""

        if not ShenCloud.selected_vm:
            log.error('stop vm None')
        else:
            vmDict = ShenCloud.selected_vm['content']
            vmIndex = ShenCloud.selected_vm['index']

        if not cmp(vmDict['state'], 'up'):
            self.waiting_state(vmIndex, vmDict['name'], 'down')

        with self.mutex_send:
            self.conn_send.send(('stop', (vmDict['name'], vmDict['id'],)))

    def on_shutdown_clicked(self, widget, data=None):
        """shutdown virtual machine"""

        if not ShenCloud.selected_vm:
            log.error('shutdown vm None')
        else:
            vmDict = ShenCloud.selected_vm['content']
            vmIndex = ShenCloud.selected_vm['index']

        if not cmp(vmDict['state'], 'up'):
            self.waiting_state(vmIndex, vmDict['name'], 'down')

        with self.mutex_send:
            self.conn_send.send(('shutdown', (vmDict['name'], vmDict['id'],)))

    def on_about_clicked(self, widget):
        """build about dialog and run"""

        dia_about = aboutdialog.About(self.gladefile['aboutdialog'])
        dia_about.run()

    def on_connect_clicked(self, widget, data=None):
        """connect virtual machine"""

        if False: #not self.admin_allow and self.user.startswith('admin@'):
            vm_id = ShenCloud.selected_vm['content']['id']
            vm, _ = self.get_vm(ShenCloud.vms_list, vm_id)
            vm_name = vm['name']
            tcm_dialog = DialogWith1Button(btn1_label='放弃', btn1_ret='CANCEL')
            tcm_dialog.set_label_text('请等待虚拟机用户授权...')
            gobject.timeout_add(1, self.tcm_dialog_run, tcm_dialog)
            self.conn_query_timer = gobject.timeout_add(500,
                                                        self.connect_query,
                                                        tcm_dialog,
                                                        vm_id,
                                                        vm_name)
        else:
            self.connect_vm()

    def tcm_dialog_run(self, tcm_dialog):
        ret = tcm_dialog.run()
        if ret:
            self.connect_vm()
        else:
            if self.conn_apply_timer:
                gobject.source_remove(self.conn_apply_timer)
                self.conn_apply_timer = None
            self.conn_apply = False
            if self.conn_query_timer:
                gobject.source_remove(self.conn_query_timer)
                self.conn_query_timer = None
            self.start_query = False

            with self.mutex_send:
                self.conn_send.send(('drop_conn', None))
                log.info('main send drop conn aplly msg to subprocess.')

        return False

    def connect_query(self, tcm_dialog, selected_vm_id, vm_name):

        if not self.start_query:
            self.start_query = True
            if self.conn_apply_timer:
                gobject.source_remove(self.conn_apply_timer)
                self.conn_apply_timer = None
                self.conn_apply = False

            with self.mutex_send:
                self.conn_send.send(('query_vm', (selected_vm_id, vm_name)))
                log.info('main send query vm msg to subprocess.')

        events = self.poller.poll(10)
        for fd, event in events:
            if fd == self.conn_recv.fileno() and event & select.POLLIN:
                with self.mutex_recv:
                    msg_type, msg_data = self.conn_recv.recv()

                if msg_type == 'query_vm':
                    log.info('recv query vm result from subprocess.')
                    ret, user_info, err_code = msg_data
                    if ret:  # query failed
                        tcm_dialog.set_label_text(err_code)
                        tcm_dialog.set_okbtn_label('确定')
                    else:  # query successful
                        self.conn_apply_timer = gobject.timeout_add(
                            1,
                            self.connect_request,
                            tcm_dialog,
                            user_info,
                            vm_name)
                else:
                    log.error('msg type is not matches when recv query vm result msg.')

                self.start_query = False
                return False

        return True

    def connect_request(self, tcm_dialog, user_info, vm_name):
        if not self.conn_apply:
            self.conn_apply = True
            with self.mutex_send:
                self.conn_send.send(('apply_conn', (user_info, vm_name)))
                log.info('send conn apply msg to subprocess.')

        events = self.poller.poll(10)
        for fd, event in events:
            if fd == self.conn_recv.fileno() and event & select.POLLIN:
                with self.mutex_recv:
                    msg_type, msg_data = self.conn_recv.recv()

                if msg_type == 'apply_conn':
                    log.info('recv conn apply result msg from subprocess.')
                    ret, data = msg_data
                    if ret:
                        if not data or data.strip('\n') == 'False':
                            tcm_dialog.set_label_text('对方拒绝您的连接请求！')
                            tcm_dialog.set_okbtn_label('确定')
                        elif data.strip('\n') == 'True':
                            tcm_dialog.msg_dialog.response(gtk.RESPONSE_OK)
                        else:
                            tcm_dialog.set_label_text('错误的授权信息！')
                            tcm_dialog.set_okbtn_label('确定')
                    else:
                         tcm_dialog.set_label_text('与虚拟机用户通信失败！')
                         tcm_dialog.set_okbtn_label('确定')
                else:
                    tcm_dialog.set_label_text('与虚拟机用户通信失败！')
                    tcm_dialog.set_okbtn_label('确定')

                self.conn_apply = False
                return False

        return True

    def connect_vm(self, vmDict=None):

        ShenCloud.connect_exit = False
        ShenCloud.connect_start = True
        ShenCloud.connect_response = -999
        ShenCloud.percent = 0.05
        self.this_vm_id = None
        selected_vm_id = None
        self.connect_time = time.time()
        self.move_count = 1000
        self.wait_connect = True
        self.connect_vm_name = ''
        if self.identity_flag == "admin":
            if vmDict:
                selected_vm_id = vmDict['id']
                self.connect_vm_name = vmDict['name']
            else:
                vm = ShenCloud.selected_vm['content']
                selected_vm_id = vm['id']
                self.connect_vm_name = vm['name']

        self.__connect_dialog_refresh = gobject.timeout_add(1, self.dia_connect_run, vmDict)
        self.__connect_show_timer_id = gobject.timeout_add(500, self.connect_show, selected_vm_id)
        return True

    def set_action_info(self, info):
        #with open('/var/action.conf', 'w') as f:
        #    f.writelines(info)
        log.debug("send action '%s' to tcm" % info)
        self.action.send(info)

    def dia_connect_run(self, vmDict):
        self.dia_connect = progressdialog.Refresh(self.gladefile['progressdialog'])
        self.dia_connect.btn_cancel = self.dia_connect.dialog.add_button("放弃", gtk.RESPONSE_CANCEL)
        self.dia_connect.lbl_vm.set_text('正在获取云桌面信息...')
        self.dia_connect.progressbar.set_fraction(0.05)
        ShenCloud.connect_response = self.dia_connect.dialog.run()

        # Revised by zxx 20150602
        self.connect_flag = False
        self.dia_connect.lbl_vm.set_text('取消云桌面连接...')
        self.dia_connect.btn_cancel.set_sensitive(False)
        with self.mutex_send:
            self.conn_send.send(('stop_connect', None))
        self.dia_connect.destroy()
        self.dia_connect = None

        self.set_action_info("vm_disconn")
        ShenCloud.connect_exit = True

        if self.__connect_show_timer_id:
            gobject.source_remove(self.__connect_show_timer_id)
            self.__connect_show_timer_id = None
        if self.__wait_connect_timer_id:
             gobject.source_remove(self.__wait_connect_timer_id)
             self.__wait_connect_timer_id = None

        if self.identity_flag in ["student", "teacher"]:
            self.logout()
        # Connect at login window
        if self.identity_flag == "admin":
            if vmDict:
                self.logout()
            else:
                self.update_vms_send.send(('update_vms', DEFAULT_UPDATE_INTERVAL))
        return False

    def logout(self):
        self.is_login = False
        try:
            self.mutex_send.acquire()
            self.conn_send.send(('logout', None))
            self.set_action_info("user_logout")
        finally:
            self.mutex_send.release()

    def connect_show(self, selected_vm_id=None):
        if ShenCloud.connect_exit:
            return False
        if ShenCloud.connect_start:
            self.__checkpowerkey()
            with self.mutex_send:
                if selected_vm_id is None:  # 非管理员,没有选择的虚拟机
                    log.info("connect_show send 'connect' to loginprocess")
                    self.conn_send.send(('connect', (None, self.identity_flag)))
                else:
                    self.this_vm_id = selected_vm_id
                    self.conn_send.send(('connect',
                                        (selected_vm_id,
                                         self.identity_flag)))
                self.dia_connect.lbl_vm.set_text('通过神云SYP协议连接虚拟机...')

            try:
                self.mutex_server_send.acquire()
                action_time = time.strftime('%Y-%m-%d %H:%M:%S')
                self.server_conn_send.send(('vm_conn', (self.user, self.connect_vm_name, action_time)))
            finally:
                self.mutex_server_send.release()

        ShenCloud.connect_start = False

        self.dia_connect.progressbar.set_fraction(ShenCloud.percent)
        ShenCloud.percent += 0.05
        if ShenCloud.percent > 1:
            ShenCloud.percent = 0.0
        if self.wait_connect:
            self.wait_connect = False
            log.info("wait_connect_return start")
            self.__wait_connect_timer_id = gobject.timeout_add(100, self.wait_connect_return, selected_vm_id)

            self.set_action_info("vm_conn")

        if self.move_count:
            self.move_count -= 1
            return True
        else:
            self.dia_connect.lbl_vm.set_text('连接超时，请检查网络。')
            self.connect_flag = False
            try:
                self.mutex_send.acquire()
                self.conn_send.send(('timeout', None))
            finally:
                self.mutex_send.release()
            if gtk.RESPONSE_CANCEL == ShenCloud.connect_response and gtk.RESPONSE_CLOSE == ShenCloud.connect_response:
                if self.identity_flag == "student" or self.identity_flag == "teacher":
                    log.debug("send logout msg")
                    self.logout()

            return False

    def fill_history_users(self):
        self.loginwin.user_list = get_user_list("/var/users.conf")
        self.loginwin.liststore.clear()
        for user in self.loginwin.user_list:
            self.loginwin.liststore.append([user["username"], ""])
        self.loginwin.liststore.append(["--- 删除所有账户 ---", ""])

    def wait_connect_return(self, selected_vm_id):
        self.fill_history_users()
        events = self.poller.poll(10)
        for fd, event in events:
            if fd == self.conn_recv.fileno() and event & select.POLLIN:
                with self.mutex_recv:
                    msg_type, msg_data = self.conn_recv.recv()
                log.info("wait_connect_return recv: %s" % msg_type)
                if msg_type == 'connect':
                    this_vm_id, retcode, detail, vm_name = msg_data
                    self.dia_connect.response(gtk.RESPONSE_OK)
                    self.connect_flag = False
                    if not retcode:
                        log.error('user: %s connect vm: %s failed. detail: %s.', self.user, vm_name, detail)
                        return False
                    else:
                        if retcode == 10:
                            self.connect_flag = False
                            log.info("链接异常!")
                            err_dialog = DialogWith1Button(btn1_label='确定', btn1_ret='CANCEL')
                            err_dialog.set_label_text('链接异常，请手动链接!')
                            gobject.timeout_add(1, err_dialog.run)
                            return False

                        elif retcode == 0xffffffff:
                            self.connect_flag = False
                            log.info("User: %s connect vm: %s failed!", self.user, vm_name)
                            err_dialog = DialogWith1Button(btn1_label='确定', btn1_ret='CANCEL')
                            err_dialog.set_label_text('链接异常，请手动链接或者联系管理员!')
                            gobject.timeout_add(1, err_dialog.run)

                        elif retcode == 0xfffffffe:
                            self.connect_flag = False
                            if self.identity_flag == "student":
                                log.info("teacher is teaching by using your computer")
                        elif retcode == 0xfffffffd:
                            self.connect_flag = False
                            log.info("User: %s connect vm: %s timeout!", self.user, vm_name)

                        else:
                            log.info("User: %s connect vm: %s successful", self.user, vm_name)
                        return False
                else:
                    return True
            else:
                return True
        else:
            return True

    def on_conn_desktop_rapid(self, widget, param1, param2):
        """rapid connect desktop when user double clicks a vm or press keys:Space,Shift+Space,Return or Enter"""

        model, selectiter = self.vmselect.get_selected()
        if selectiter:
            select_vm_name = model.get(selectiter, 1)[0]
            for tmp_vm in ShenCloud.vms_list:
                if not cmp(select_vm_name, tmp_vm['name']):
                    if tmp_vm['state'] == 'up' or tmp_vm['state'] == 'powering_up':
                        self.mainwin.btn_conn.emit("clicked")
                    elif tmp_vm['state'] == 'down':
                        self.mainwin.btn_start.emit("clicked")
                    else:
                        pass

    def on_key_press(self, widget, event):
        """key press event
        'F4' == key: call settingDialog
        202 == event.hardware_keycode: press power key
        """
        key = gtk.gdk.keyval_name(event.keyval)
        if 'F4' == key:
            self.pwdwnd = passwd.PasswdWindow()
            if self.pwdwnd.is_validate():
                log.debug("Open setting dialog")
                wlan_on = self.is_wlan_on()
                if self.user:
                    if self.identity_flag == "student" or self.identity_flag == "admin":
                        setting = settingdialog.SettingDialog(self.__pwdkey, self.gladefile,
                                                              self.setting_conn_send, self.setting_conn_recv,
                                                              self.server_conn_send, self.server_conn_recv,
                                                              self.mutex_setting_send, self.mutex_setting_recv,
                                                              0, wlan_on)
                    elif self.identity_flag == "teacher":
                        self.teacher_flag = True
                        setting = settingdialog.SettingDialog(self.__pwdkey, self.gladefile,
                                                              self.setting_conn_send, self.setting_conn_recv,
                                                              self.server_conn_send, self.server_conn_recv,
                                                              self.mutex_setting_send, self.mutex_setting_recv,
                                                              self.teacher_flag, wlan_on)
                else:
                    setting = settingdialog.SettingDialog(self.__pwdkey, self.gladefile,
                                                          self.setting_conn_send, self.setting_conn_recv,
                                                          self.server_conn_send, self.server_conn_recv,
                                                          self.mutex_setting_send, self.mutex_setting_recv,
                                                          0, wlan_on)

                ret = setting.run()

                # Check user lock status
                if setting.get_unlock_status() or self.loginwin.check_user_empty():
                    log.debug("Unlock user input")
                    self.user_login_unlock(True)
                else:
                    log.debug("Lock user input")
                    self.user_login_unlock(False)

                if (gtk.RESPONSE_OK == ret):
                  #  if autologin:
                  #      self.loginwin.cbtn_autologin.set_active(True)
                  #  else:
                  #      self.loginwin.cbtn_autologin.set_active(False)
                    log.debug('save configure success')
                elif (gtk.RESPONSE_CANCEL == ret) or (gtk.RESPONSE_DELETE_EVENT == ret):
                    log.debug('cancel configure')
                setting = None
        elif 'Return' == key and self.loginwin.win.is_active():
            self.loginwin.btn_login.emit("clicked")
        elif 'KP_Enter' == key and self.loginwin.win.is_active():
            self.loginwin.btn_login.emit("clicked")

    def quit_mainwnd(self):
        """logout main window"""
        if self.__wait_connect_timer_id:
            gobject.source_remove(self.__wait_connect_timer_id)
            self.__wait_connect_timer_id = None
        if self.__progress_move_timer_id:
            gobject.source_remove(self.__progress_move_timer_id)
            self.__progress_move_timer_id = None
        if self.__update_vms_timer_id:
            gobject.source_remove(self.__update_vms_timer_id)
            self.__update_vms_timer_id = None

        with self.mutex_liststore:
            self.liststore.clear()

        self.mainwin.lbl_sum_vm.set_text(str(0))
        self.mainwin.lbl_curr_vm.set_text(str(0))
        self.mainwin.lbl_sum_vcpu.set_text(str(0))
        self.mainwin.lbl_curr_vcpu.set_text(str(0))
        self.mainwin.lbl_sum_vmem.set_text(str(0) + 'GB')
        self.mainwin.lbl_curr_vmem.set_text(str(0) + 'GB')
        self.mainwin.Progbar_vms.set_fraction(0)
        self.mainwin.Progbar_vcpu.set_fraction(0)
        self.mainwin.Progbar_vmem.set_fraction(0)

        ShenCloud.vms_list = []

        with self.mutex_send:
            self.conn_send.send(('logout', None))

        self.set_action_info("user_logout")

    def on_softquit_clicked(self, widget, data=None):
        """quit program"""

        self.quit_mainwnd()

        if self.mainwin:
            self.mainwin.win.destroy()
            self.mainwin = True

        if self.loginwin:
            self.loginwin.win.destroy()
            self.loginwin = True

        with self.mutex_send:
            self.conn_send.send(('exit', None))
        log.info("quit the program!")
        destroy_log()
        gtk.main_quit()

    def on_manage_clicked(self, widget, data=None):
        user = self.loginwin.entbuf_user.child.get_text()
        if user:
            try:
                cwd = self.config.get('Manage', 'path')
            except Exception:
                cwd = '/usr/share/tplManager'
            if os.path.exists(cwd):
                self.loginwin.win.hide()
                if self.loglevel:
                    cmd = 'python main.pyc -u %s -l %s' % (user, self.loglevel)
                else:
                    cmd = 'python main.pyc -u %s' % user
                log.debug("Exec: '%s' under '%s'" % (cmd, cwd))
                self.loginwin.show()
                try:
                    subprocess.Popen(cmd, cwd=cwd, shell=True).wait()
                except Exception as err:
                    log.error("Call tplManager failed: %s" % err)
            else:
                gobject.timeout_add(100, self.login_error, '功能暂不支持!')
        else:
            gobject.timeout_add(100, self.login_error, '请输入用户名!')


    def on_quit_clicked(self, widget, data=None):
        """logout main window, back to login window"""

        self.login_click_num = 0
        self.quit_mainwnd()
        action_time = time.strftime('%Y-%m-%d %H:%M:%S')
        try:
            action_time = time.strftime('%Y-%m-%d %H:%M:%S')
            self.mutex_server_send.acquire()
            self.server_conn_send.send(('user_logout', (self.user, '-', action_time)))
        finally:
            self.mutex_server_send.release()
        if self.user:
            log.info("User: %s quit the main window!", self.user)
            self.user = None

        self.fill_history_users()

        self.loginwin.show()
        self.mainwin.win.hide()

        return False

    def on_poweroff_clicked(self, widget, data=None):
        """Turn off the system"""
        if isinstance(data, str):
            if not cmp(data, "loginwin"):
                log.debug("press power off key in login window")
            elif not cmp(data, "mainwin"):
                log.debug("press power off key in main window")
        if self.__update_vms_timer_id:
            gobject.source_remove(self.__update_vms_timer_id)
            self.__update_vms_timer_id = None
        msgdia_poweroff = poweroffdialog.PowerOff(0)
        ret = msgdia_poweroff.run()
        if ret:
            if self.identity_flag == "admin" and self.identity_flag == "teacher":
                if self.mainwin:
                    self.mainwin.btn_quit.emit('clicked')
            try:
                self.mutex_server_send.acquire()
                self.server_conn_send.send(('poweroff', None))
            finally:
                self.mutex_server_send.release()
            time.sleep(1)
            log.info("exec the cmd 'poweroff' to shutdown the teacher client")
            os.system("sudo poweroff")

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
        except Exception ,err:
            log.error("An error in get teacher server! reason: %s" % err)
            server_ip, server_port = "", ""

        return server_ip, server_port

    def send_request_teaServer(self, method="GET", path="/", body=None):
        """send a request to teacher server
        """
        server_ip, server_port = self.get_tea_server()
        log.info("teacher server's ip: %s, port is: %s" % (server_ip, server_port))
        try:
            http_conn = httplib.HTTPConnection(server_ip, server_port)
        except:
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

    def http_send_poweroff_stu(self):
        """send the POST request to shutdown all computer of student
        """

        body = POWEROFF_MSG % (self.user, 'poweroff')
        path = '/client_msg/'
        method = "POST"
        self.send_request_teaServer(method, path, body)

    def get_server_ip(self):
        self.base_url = self.config.get('oVirt', 'baseurl')

        server_ip = ''
        if self.base_url.count('/'):
            p1 = self.base_url.index('/')
            if self.base_url[p1+2:].count(':'):
                p2 = self.base_url[p1+2:].index(':')
                server_ip = self.base_url[p1+2:p1+2+p2]

        return server_ip

    def close_server1(self):
        """关闭服务器并退出到登陆窗口后关机"""
        #self.close_server()

        try:
            self.mutex_send.acquire()
            self.conn_send.send(("shutdown_server", None))
        finally:
            self.mutex_send.release()
        self.mainwin.btn_quit.emit('clicked')
        #try:
        #    self.mutex_server_send.acquire()
        #    self.server_conn_send.send(('poweroff', None))
        #finally:
        #    self.mutex_server_send.release()

    def waitting_server_down(self):
        """waitting server shutdown"""
        conn_poller = select.poll()
        conn_poller.register(self.rpc_recv.fileno(), select.POLLIN)
        events = conn_poller.poll(10)
        for fd, event in events:
            if fd == self.rpc_recv.fileno() and event & select.POLLIN:
                try:
                    self.mutex_recv.acquire()
                    msg_type, msg_data = self.rpc_recv.recv()
                finally:
                    self.mutex_recv.release()

                if msg_type == "waitting_server_down":
                    os.system("sudo poweroff")
                    log.info("exec the cmd 'poweroff' to shutdown the os")
                    return True
            return False
        return True

    def show_dialog(self):
        self.network_dialog1 = checknetdialog.CheckNet()
        self.network_dialog1.lbl_msg.set_text("正在关闭服务器...请稍候")
        self.network_dialog1.btn_cancel = self.network_dialog1.dialog.add_button("关闭", gtk.RESPONSE_CANCEL)
        self.network_dialog1.run()
        return False

    def on_poweroff_all_clicked(self, widget, data=None):
        msgdia_poweroff = poweroffdialog.PowerOff("tech_and_stu")
        ret = msgdia_poweroff.run()
        if ret:
            try:
                self.mutex_send.acquire()
                self.conn_send.send(('terminate_demon', None))
            finally:
                self.mutex_send.release()

            # gobject.timeout_add(1, self.terminate_demon)
            gobject.timeout_add(2, self.poweroff_stu)

    def poweroff_stu(self):
        msgdia_poweroff = poweroffdialog.PowerOff("server")
        ret = msgdia_poweroff.run()
        if ret:
            try:
                self.mutex_send.acquire()
                self.conn_send.send(('poweroff_stu', None))
            finally:
                self.mutex_send.release()

            # self.http_send_poweroff_stu()  # 关闭教师端和学生端
            gobject.timeout_add(1, self.show_dialog)
            gobject.timeout_add(1000, self.close_server1)
            gobject.timeout_add(1000, self.waitting_server_down)
        else:
            self.http_send_poweroff_stu()  # 关闭教师端和学生端
            self.mainwin.btn_quit.emit('clicked')
            try:
                self.mutex_server_send.acquire()
                self.server_conn_send.send(('poweroff', None))
            finally:
                self.mutex_server_send.release()
            time.sleep(0.5)
            os.system("sudo poweroff")
            log.info("exec the cmd 'poweroff' to shutdown the os")

    def on_select_wlan(self, treeselection, data=None):
        model, selectiter = treeselection.get_selected()
        if selectiter:
            self.select_wlan_name = model.get(selectiter, 0)[0]
        with open(WPA_WAY, 'r') as f:
            i = 0
            line = f.readlines()
            for li in line:
                if "\tssid=" in li:
                    line[i] = "\tssid=\"%s\"\n" % self.select_wlan_name.strip('\n')
                    break
                i += 1
        with open(WPA_WAY, 'w') as f:
            f.writelines(line)

    def on_select_changed(self, treeselection, data=None):
        """changes the selected virtual machine"""
        model, selectiter = treeselection.get_selected()
        if selectiter:
            select_vm_name = model.get(selectiter, 1)[0]
            #log.debug("vm select changed, selecting vm: %s", select_vm_name)
            for index, tmp_vm in enumerate(ShenCloud.vms_list):
                if not cmp(select_vm_name, tmp_vm['name']):
                    ShenCloud.selected_vm = {'index': index, 'content':tmp_vm}
                    break
            self.update_buttons(tmp_vm)

    def update_buttons(self, selected_vm):
        """update buttons status
        when changes the selected vm, update buttions status
        """

        if not selected_vm:
            return

        self.mainwin.btn_start.set_sensitive(False)
        self.mainwin.btn_stop.set_sensitive(False)
        self.mainwin.btn_shutdown.set_sensitive(False)
        self.mainwin.btn_conn.set_sensitive(False)
        state = selected_vm['state']

        if state == 'wait_for_launch':
            self.mainwin.btn_start.set_sensitive(True)
            self.mainwin.btn_shutdown.set_sensitive(True)
            self.mainwin.btn_stop.set_sensitive(True)
            self.mainwin.btn_conn.set_sensitive(False)
    #        self.mainwin.btn_quit.set_sensitive(False)
    #        return
        elif state == 'suspended':
            self.mainwin.btn_start.set_sensitive(True)
            self.mainwin.btn_shutdown.set_sensitive(True)
            self.mainwin.btn_stop.set_sensitive(True)
            self.mainwin.btn_conn.set_sensitive(False)
        elif state == 'saving_state' or state == 'restoring_state':
            self.mainwin.btn_start.set_sensitive(False)
            self.mainwin.btn_stop.set_sensitive(False)
            self.mainwin.btn_shutdown.set_sensitive(False)
            self.mainwin.btn_conn.set_sensitive(False)
        elif state == 'up' or state == 'powering_up':
            self.mainwin.btn_stop.set_sensitive(True)
            self.mainwin.btn_shutdown.set_sensitive(True)
            self.mainwin.btn_conn.set_sensitive(True)
            self.mainwin.btn_quit.set_sensitive(True)
        elif state == 'powering_down':
            self.mainwin.btn_stop.set_sensitive(True)
            self.mainwin.btn_shutdown.set_sensitive(True)
            self.mainwin.btn_conn.set_sensitive(False)
        elif state == 'down':
            self.mainwin.btn_start.set_sensitive(True)
        else:
            return

    def checkautologin(self):
        """check autologin option status"""

        autologin = self.loginwin.cbtn_autologin.get_active()
        if autologin:
            log.info('autologin...')
            self.loginwin.btn_login.emit("clicked")

    def __validcheck(self):
        """check the usrname and password"""

        errstr = ''
        if not self.loginwin.entbuf_user.child.get_text().strip() or \
           not self.loginwin.entbuf_pwd.get_text().strip():
            errstr = '用户名或密码不能为空！'
            self.loginwin.lbl_warn.set_text("错误：%s" % errstr)
            log.debug("username or password can not be empty!")
            return False
        return True

    def __checkpowerkey(self):
        try:
            retcode = subprocess.call("powerkey", shell=True)

            if retcode == 256:
                log.debug('short press')
            elif retcode == 512:
                log.debug("long press")
        except OSError as e:
            log.debug("powerkey cmd execution failed: %s", e)

        return True

def main():
    gtk.main()

if "__main__" == __name__:
    #subprocess.Popen('/etc/init.d/networking restart', shell=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', action = 'store',
                        dest = 'simple_value')
    result = parser.parse_args()
    #settingdialog.save_teacher_url('')
    log_value = result.simple_value
    if log_value:
        if log_value.upper() == 'DEBUG':
            init_log(logging.DEBUG)
        elif log_value.upper() == 'INFO':
            init_log(logging.INFO)
        elif log_value.upper() == 'WARNING':
            init_log(logging.WARNING)
        elif log_value.upper() == 'ERROR':
            init_log(logging.ERROR)
        elif log_value.upper() == 'CRITICAL':
            init_log(logging.CRITICAL)
        else:
            init_log(logging.INFO)
    else:
        init_log(logging.INFO)

    if os.path.exists(CONF_FILE) and os.path.getsize(CONF_FILE):
        cmd1 = 'sudo cp -f %s %s' % (CONF_FILE, CONF_FILE_BAK)
    else:
        cmd1 = 'sudo cp -f %s %s' % (CONF_FILE_BAK, CONF_FILE)
    subprocess.call(cmd1, shell=True)

    config = ConfigParser.ConfigParser()
    config.read(CONF_FILE)
    settings = ConfigParser.ConfigParser()
    settings.read(SET_CONF_FILE)

    ShenCloud(config, settings, loglevel=log_value)
    main()

