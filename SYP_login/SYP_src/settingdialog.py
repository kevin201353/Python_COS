#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 ShenCloud Inc.
#

"""
config and get the configure info of the settingdialog
"""

import pygtk
pygtk.require('2.0')
import gtk
import time
import os
import sys
import gobject
import subprocess
import logging

import ConfigParser
import ifconfig
import basictools as bt
import advance
import aboutdialog
import settingerrordialog
import wlandialog
from wlandialog import read_wlan_essid_and_passwd
from basictools import ip_format_check
from cusdialog import DialogWith1Button

log = logging.getLogger(__name__)

IDPATH = '/sys/mac_id/mac_id'
UPGRADE_INFO = '/var/upgrade.info'
# SLEEP_TIME = os.path.expanduser('~') + '/.xscreensaver'
SLEEP_TIME = '/home/linaro/.xscreensaver'
# add by zhanglu
HDMI_FLAG_FILE = "/proc/cmdline"
HDMI_RESOLUTION_INFO = '/sys/devices/platform/mxc_hdmi/resolution'
# end
RESOLUTION_INFO = '/sys/bus/platform/drivers/imx-ch7033/resolution'
DISPMODE = '/etc/init.d/dispmode'
BRIGHTNESS = '/sys/devices/platform/pwm-backlight.0/backlight/pwm-backlight.0/brightness'
MODE = '/sys/bus/platform/drivers/imx-ch7033/mode'
DNS = '/etc/resolv.conf'
BRIGHTNESS_VALUE = '/var/brightness'

resolution_dict = {}
#resolution_dict = {0: '1920 x 1080', 1: '1680 x 1050',
#                   2: '1440 x 900',  3: '1366 x 768',
#                   4: '1280 x 1024', 5: '1024 x 768',
#                   6: '800 x 600'}
flag = 1
n = 0
def insert_combobox_from_list(combox, interface_name, wlan_on=False):
    """Setup a ComboBox or ComboBoxEntry baseed on a list of strings."""

    model = gtk.ListStore(str)
    for i in interface_name:
        if (wlan_on and i.startswith('eth')) \
           or ((not wlan_on) and (i.startswith('wlan'))):
            #cmd = "sudo ifconfig %s down" % i
            #os.system(cmd)
            continue
        model.append([i])
    combox.clear()
    combox.set_model(model)
    if type(combox) == gtk.ComboBoxEntry:
        combox.set_text_column(0)
    elif type(combox) == gtk.ComboBox:
        cell = gtk.CellRendererText()
        combox.pack_start(cell, True)
        combox.add_attribute(cell, 'text', 0)

def insert_essid_combox_from_list(combox, essid_list):
    """Setup a ComboBox or ComboBoxEntry baseed on a list of strings."""

    model = gtk.ListStore(str)
    for i in essid_list:
        model.append([i])
    combox.clear()
    combox.set_model(model)
    if type(combox) == gtk.ComboBoxEntry:
        combox.set_text_column(0)
    elif type(combox) == gtk.ComboBox:
        cell = gtk.CellRendererText()
        combox.pack_start(cell, True)
        combox.add_attribute(cell, 'text', 0)

def insert_resolution_combobox(combox):
    """Setup a ComboBox or ComboBoxEntry baseed on a list of strings."""
    global resolution_dict

    dispmode_info = []
    hdmi_flag = False
    if os.path.exists(HDMI_FLAG_FILE):
        with open(HDMI_FLAG_FILE) as hdmi_flag_file:
            hdmi_flag_info = hdmi_flag_file.read()
        if "dev=hdmi" in hdmi_flag_info:
            hdmi_flag = True

    if hdmi_flag and os.path.exists(HDMI_RESOLUTION_INFO):
        with open(HDMI_RESOLUTION_INFO, 'r') as dispmode_info_file:
            dispmode_info = dispmode_info_file.readlines()
    elif not hdmi_flag and os.path.exists(RESOLUTION_INFO):
        with open(RESOLUTION_INFO, 'r') as dispmode_info_file:
            dispmode_info = dispmode_info_file.readlines()

    for line in dispmode_info:
        strr = line.strip()
        try:
            mode, dispmode_msg = strr.split(':')
        except:
            continue
        num, resolution = int(mode), dispmode_msg.strip()
        resolution_dict[num] = resolution
        if not resolution_dict:
            continue
        num, resolution = int(mode), dispmode_msg.strip()
        resolution_dict[num] = resolution
    if not resolution_dict:
        resolution_dict = {0: '1920 x 1080', 1: '1680 x 1050',
                           2: '1440 x 900',  3: '1366 x 768',
                           4: '1280 x 1024', 5: '1024 x 768',
                           6: '800 x 600'}


    model = gtk.ListStore(str)
    for k,v in resolution_dict.items():
        model.append([v])
    combox.set_model(model)
    if type(combox) == gtk.ComboBoxEntry:
        combox.set_text_column(0)
    elif type(combox) == gtk.ComboBox:
        cell = gtk.CellRendererText()
        combox.pack_start(cell, True)
        combox.add_attribute(cell, 'text', 0)
    return n, flag

def save_teacher_url(url):

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

def putdown_netif(if_name):
    if if_name:
        subprocess.Popen("sudo kill `ps aux | grep dhclient | grep %s | grep -v grep | awk '{print $2}'` > /dev/null 2>&1" % if_name,
                         shell=True)
        subprocess.Popen("sudo ifconfig %s 0.0.0.0 > /dev/null 2>&1" % if_name, shell=True)
        subprocess.Popen("sudo ifconfig %s down > /dev/null 2>&1" % if_name, shell=True)

class SettingDialog(object):
    """ Class of Setting Dialog"""

    def __init__(self, pwd_key, gladefile, conn_send, conn_recv,
                 server_conn_send, server_conn_recv, mutex_send, mutex_recv,
                 teacher_flag, wlan_on=False):
        # self.__ovirt_connect = ovirt_connect
        # self.__config = ovirt_connect.config
        self.config = ConfigParser.ConfigParser()
        self.config.read('/var/ovirt.conf')
        self.conn_send = conn_send
        self.conn_recv = conn_recv
        self.server_conn_send = server_conn_send
        self.server_conn_recv = server_conn_recv
        self.mutex_send = mutex_send
        self.mutex_recv = mutex_recv
        self.__pwd_key = pwd_key
        self.gladefile = gladefile
        self.teacher_flag = teacher_flag
        self.__nic_dict = {}
        self.time_update_id = None
        self.time_value_changed = None
        self.baseUrl = None
        self.tmppwd = None
      #  self.autoLogin = False
        self.rguest = False
        self.scal = False
        self.unlock = False
        self.Username = None
        self.Password = None
        self.wlanwifi = None
        self.ServerIP = None
        self.Port = None
        self.name = None
        self.dpt_name = None
        self.upgrade_addr = None
        self.teacher_ip = None
        self.teacher_port = None
        self.backlight_value = 0.00
        self.resolution_val_old = -1
        self.resolution_val_new = -1
        self.wlan_on = wlan_on
        self.net_mode_changed = False
        self.class_url_info = None
        self.load_gladexml()
#        self.btn_ok = self.dia_setting.add_button("OK", gtk.RESPONSE_OK)
#        self.btn_cancel = self.dia_setting.add_button("Cancel", gtk.RESPONSE_CANCEL)
        self.btn_ok.connect("clicked", self.on_okbtn_clicked)
        self.btn_cancel.connect("clicked", self.on_cancel_btn_clicked)
        self.btn_unlock.connect("clicked", self.on_unlockbtn_clicked)
        self.btn_advance.connect("clicked", self.on_advancebtn_clicked)
        self.btn_about.connect("clicked", self.on_aboutbtn_clicked)
        self.btn_server_save.connect("clicked", self.on_serverbtn_clicked)
        self.btn_upgrade_save.connect("clicked", self.on_upgradebtn_clicked)
        self.cbtn_wlan.connect("toggled", self.on_wlan_toggled)
        self.btn_connwlan.connect("clicked", self.on_conn_wlan_clicked)
        self.dia_setting.connect("key-press-event", self.on_key_press)
        self.dia_setting.set_title("")
        self.btn_teacher_save.connect("clicked", self.on_teacherbtn_clicked)
        # Keep it stayed at the top of the parent window dialog,until closing.
        self.dia_setting.set_modal(True)
        # Don't Full screen
        # self.dia_setting.set_decorated(False)
        # init ip address entry
        self.entbuf_ip.set_sensitive(False)
        # Control(ipentry) is set to not response status, that means you can't
        # click and select it or make it gains focus. Visually, the controls
        # will be displayed in gray
        self.entbuf_mask.set_sensitive(False)
        self.entbuf_gateway.set_sensitive(False)
        self.entbuf_dns.set_sensitive(False)

        self.load_config()

        self.load_teacher_url()

        # init system time and sleep time
        self.insert_Spin_button_from_datetime(self.spinbtn_year,
                                              self.spinbtn_month,
                                              self.spinbtn_day,
                                              self.spinbtn_hour,
                                              self.spinbtn_minute,
                                              self.spinbtn_sec,
                                              self.spinbtn_sleep_hour,
                                              self.spinbtn_sleep_minute)

        # init graphic
        try:
            # dns list
            self.__dnsinfo = bt.read_dnsfile()

            self.entbuf_url.set_text(self.ServerIP)
            self.entbuf_port.set_text(self.Port)
            if (self.rguest):
                self.cbtn_reguest.set_active(True)
            if (self.scal):
                self.cbtn_scaling.set_active(True)
            if (self.wlanwifi):
                self.cbtn_wlan.set_active(True)
            else:
                self.cbtn_wlan.set_active(False)
                self.__nic_dict = bt.read_file(list(ifconfig.list_ifs()) + ['lo'])
                self.disable_wlan()
                self.config_net_ipinfo()
            ### modify by chenyao, move these to enable_wlan and disable_wlan functions.
            # interface list
            #self.__nic_dict = bt.read_file(list(ifconfig.list_ifs()) + ['lo'])
            # import interface list to combobox
            #insert_combobox_from_list(self.combox_interface, list(ifconfig.list_ifs()), wlan_on=self.wlanwifi)
            #self.combox_interface.set_active(0)
            #self.__cur_interface_name = self.combox_interface.get_active_text()
            self.entry_name.set_text(self.name)
            self.entry_dname.set_text(self.dpt_name)
            self.entbuf_user.set_text(self.Username)
            self.entbuf_pwd.set_text(bt.decrypt(self.__pwd_key, self.Password))
        except Exception, err:
            log.warning('%s', err)

        self.frame_backlight.set_visible(True)
        self.frame_resolution.set_visible(False)
        self.hscale_backlight.set_sensitive(True)
        value = os.popen('cat %s' % BRIGHTNESS_VALUE)
        self.backlight_value = int(value.read())
        value = (self.backlight_value-25) / 230.00
        value = float('%.2f' % value)
        self.adjust_backlight.set_value(value)

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
            if '8000' == server_port:
                self.entbuf_upgrade.set_text(server_ip)
            else:
                self.entbuf_upgrade.set_text(strr)

    def enable_wlan(self):
        if not self.wlan_on:
            self.wlan_on = True
            os.system("sudo insmod /usr/share/wifi/rtl8188eu.ko")

            try:
                subprocess.check_output("sudo ifconfig wlan0 up", shell=True)
            except:
                os.system("sudo rmmod rtl8188eu.ko")
                self.cbtn_wlan.set_active(False)
                errordlg = DialogWith1Button(btn1_label='确定', btn1_ret='OK')
                errordlg.set_label_text("未检测到无线网卡！")
                errordlg.run()
                return False
        self.btn_connwlan.set_sensitive(True)
        self.combox_wlan.set_sensitive(True)

        wlan_list = os.popen("sudo iwlist wlan0 scan | grep ESSID | grep '\"' | awk -F '\"' '{print $2}'").readlines()
        wlan_list = [essid.strip('\n') for essid in wlan_list]
        try:
            putdown_netif('eth0')
        except Exception, err:
            pass
        insert_combobox_from_list(self.combox_interface, list(ifconfig.list_ifs()), wlan_on=True)
        self.combox_interface.set_active(0)
        self.reload_network_setting()
        self.rbtn_static.set_sensitive(False)
        wlan_dict, index = {}, 0
        for ssid in wlan_list:
            wlan_dict[ssid] = index
            index += 1
        insert_essid_combox_from_list(self.combox_wlan, wlan_list)
        select_ssid, _ = read_wlan_essid_and_passwd()
        try:
            self.combox_wlan.set_active(wlan_dict[select_ssid])
        except Exception, err:
            pass

        return False

    def disable_wlan(self):
        self.btn_connwlan.set_sensitive(False)
        if self.wlan_on:
            self.wlan_on = False
            os.system("sudo ifconfig wlan0 down")
            os.system("sudo rmmod rtl8188eu.ko")
            os.system("sudo killall wpa_supplicant > /dev/null 2>&1")
        self.combox_wlan.set_sensitive(False)
        insert_combobox_from_list(self.combox_interface, list(ifconfig.list_ifs()))
        self.combox_interface.set_active(0)
        self.reload_network_setting()
        self.rbtn_static.set_sensitive(True)
        subprocess.Popen("sudo ifconfig %s up" % self.__cur_interface_name, shell=True)
        subprocess.Popen("sudo ifup %s" % self.__cur_interface_name, shell=True)

    def load_teacher_url(self):

        with open(UPGRADE_INFO, 'r') as teacher_info_file:
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
            if '8090' == teacher_server_port:
                self.entbuf_teacher.set_text(teacher_server_ip)
            else:
                self.entbuf_teacher.set_text(strr)
        if self.teacher_flag:
            try:
                class_ip = self.config.get('Class', 'class_url')
            except:
                fp = open('/var/ovirt.conf', 'a')
                fp.write('\nclass_url = ')
                fp.close()
                self.config.read('/var/ovirt.conf')
                class_ip = self.config.get('Class', 'class_url')
            finally:
                self.entbuf_class.set_text(class_ip)

    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            setting_name = self.config.get('Config', 'logo_name')
            if self.teacher_flag:
                arr = setting_name + "_settingdialog_e_t.glade"
            else:
                arr = setting_name + "_settingdialog_e.glade"
            self.builder.add_from_file(arr)
        except:
            log.error("Failed to load UI XML fle: settingdialog.glade")
            sys.exit(1)
        self.builder.connect_signals(self)
        self.dia_setting = self.builder.get_object("settingdialog")
        self.btn_ok = self.builder.get_object("btn_ok")
        self.btn_cancel = self.builder.get_object("btn_cancel")
        self.entbuf_url = self.builder.get_object("urlentry")
        self.entbuf_port = self.builder.get_object("portentry")
        self.entbuf_user = self.builder.get_object('userentry')
        self.entbuf_pwd = self.builder.get_object('pwdentry')
#        self.cbtn_autologin = self.builder.get_object('autologinchkbtn')
        self.cbtn_reguest = self.builder.get_object('resize_guest_btn')
        self.cbtn_scaling = self.builder.get_object('scalingbtn')
        self.rbtn_dhcp = self.builder.get_object('dhcpradiobtn')
        self.cbtn_wlan = self.builder.get_object("wlancheckbutton")
        self.rbtn_static = self.builder.get_object('staticradiobtn')
        self.entbuf_ip = self.builder.get_object('ipentry')
        self.entbuf_mask = self.builder.get_object("maskentry")
        self.entbuf_gateway = self.builder.get_object("gatewayentry")
        self.entbuf_dns = self.builder.get_object("dnsentry")
        self.combox_wlan = self.builder.get_object("wlancombobox")
        self.combox_interface = self.builder.get_object("intercombobox")
        self.spinbtn_year = self.builder.get_object("spinbtn_year")
        self.spinbtn_month = self.builder.get_object("spinbtn_month")
        self.spinbtn_day = self.builder.get_object("spinbtn_day")
        self.spinbtn_hour = self.builder.get_object("spinbtn_hour")
        self.spinbtn_minute = self.builder.get_object("spinbtn_minute")
        self.spinbtn_sec = self.builder.get_object("spinbtn_sec")
        self.spinbtn_sleep_hour = self.builder.get_object("spinbtn_sleep_hour")
        self.spinbtn_sleep_minute = self.builder.get_object("spinbtn_sleep_minute")
        self.txtview_info = self.builder.get_object("infotextview")
        self.btn_connwlan = self.builder.get_object("btn_conn_wlan")
        self.btn_advance = self.builder.get_object("advancebutton")
        self.cbtn_screensaver = self.builder.get_object("cbtn_screensaver")
        self.btn_about = self.builder.get_object("aboutbutton")
        self.entbuf_upgrade = self.builder.get_object("entry_upgrade")
        self.btn_server_save = self.builder.get_object("button_server_save")
        self.btn_unlock = self.builder.get_object("button_unlock_user")
        self.btn_upgrade_save = self.builder.get_object("button_upgrade_save")
        self.hscale_backlight = self.builder.get_object("hscale_backlight")
        self.adjust_backlight = self.builder.get_object("adjust_backlight")
        self.combox_resolution = self.builder.get_object("combobox_re")
        self.frame_backlight = self.builder.get_object("frame6")
        self.frame_resolution = self.builder.get_object("frame7")
        self.entry_name = self.builder.get_object("name_entry")
        self.entry_dname = self.builder.get_object("dname_entry")
        self.treeview_machine = self.builder.get_object("wanltreeview")
        self.entbuf_teacher = self.builder.get_object("entry_teacher")
        self.entbuf_class = self.builder.get_object("entry_class")
        self.btn_teacher_save = self.builder.get_object("button_teacher_save")

    def load_config(self):
        try:
            self.mutex_send.acquire()
            self.conn_send.send(('load_config', None))
        finally:
            self.mutex_send.release()
        try:
            self.mutex_recv.acquire()
            msg_type, msg_data = self.conn_recv.recv()
        finally:
            self.mutex_recv.release()

        if msg_type == 'load_config' and msg_data:
            (self.baseUrl, self.tmppwd, self.wlanwifi, self.rguest, self.scal, self.name,
             self.dpt_name, self.Username, self.Password, self.ServerIP,
             self.Port) = msg_data

    def insert_Spin_button_from_datetime(self,
                                         year_spinbtn,
                                         month_spinbtn,
                                         day_spinbtn,
                                         hour_spinbtn,
                                         minute_spinbtn,
                                         sec_spinbtn,
                                         sleep_hour_spinbtn,
                                         sleep_minute_spinbtn):
            """Setup spinbutton to adjust sytem time and sleep time."""

            # get datetime from system
            (year, month, day, hour, minute, sec, _, _, _) = time.localtime()

            # set SpinButton value wraps around to the oppssite limit
            # when the upper or lower limit of the range is exceede.
            year_spinbtn.set_wrap(True)
            month_spinbtn.set_wrap(True)
            day_spinbtn.set_wrap(True)
            hour_spinbtn.set_wrap(True)
            minute_spinbtn.set_wrap(True)
            sec_spinbtn.set_wrap(True)
            sleep_hour_spinbtn.set_wrap(True)
            sleep_minute_spinbtn.set_wrap(True)

            # get sleep mode
            with open(SLEEP_TIME, 'r') as sleep_time_file:
                sleep_time_setting = sleep_time_file.readlines()

                for line in sleep_time_setting:
                    if line.strip().startswith('timeout:'):
                        sleep_time = line.strip('timeout:').strip().strip('\n').split(':')
                        sleep_hour, sleep_minute = sleep_time[0], sleep_time[1]
                        break

                for line in sleep_time_setting:
                    if line.strip().startswith('mode:'):
                        mode = line.strip('mode:')
                        if 'blank' in mode:
                            self.cbtn_screensaver.set_active(True)
                        elif 'off' in mode:
                            self.cbtn_screensaver.set_active(False)
                        break

            # set spin button value
            year_adj = gtk.Adjustment(year, 0.0, 3000.0, 1.0, 100.0, 0.0)
            year_spinbtn.set_adjustment(year_adj)

            month_adj = gtk.Adjustment(month, 1.0, 12.0, 1.0, 10.0, 0.0)
            month_spinbtn.set_adjustment(month_adj)

            # different month have different days(and Run years)
            if month in [1, 3, 5, 7, 8, 10, 12]:
                day_max = 31.0
            elif month in [4, 6, 9, 11]:
                day_max = 30.0
            else:
                if ((year % 4 == 0) and (year % 100 != 0)) or (year % 400 == 0):
                    day_max = 29.0
                else:
                    day_max = 28.0

            day_adj = gtk.Adjustment(day, 1.0, day_max, 1.0, 10.0, 0.0)
            day_spinbtn.set_adjustment(day_adj)

            hour_adj = gtk.Adjustment(hour, 0.0, 23.0, 1.0, 10.0, 0.0)
            hour_spinbtn.set_adjustment(hour_adj)

            minute_adj = gtk.Adjustment(minute, 0.0, 59.0, 1.0, 10.0, 0.0)
            minute_spinbtn.set_adjustment(minute_adj)

            sec_adj = gtk.Adjustment(sec, 0.0, 59.0, 1.0, 10.0, 0.0)
            sec_spinbtn.set_adjustment(sec_adj)

            sleep_hour_adj = gtk.Adjustment(float(sleep_hour), 0.0, 9.0, 1.0, 10.0, 0.0)
            sleep_hour_spinbtn.set_adjustment(sleep_hour_adj)

            sleep_minute_adj = gtk.Adjustment(float(sleep_minute), 0.0, 59.0, 1.0, 10.0, 0.0)
            sleep_minute_spinbtn.set_adjustment(sleep_minute_adj)

            sec_spinbtn.connect("button-press-event", self.on_sec_spinbtn_press)
            minute_spinbtn.connect("button-press-event", self.on_minute_spinbtn_press)
            hour_spinbtn.connect("button-press-event", self.on_hour_spinbtn_press)

            sec_spinbtn.connect("wrapped", self.on_sec_spinbtn_wrapped, self.spinbtn_minute)
            minute_spinbtn.connect("wrapped", self.on_minute_spinbtn_wrapped, self.spinbtn_year)
            hour_spinbtn.connect("wrapped", self.on_hour_spinbtn_wrapped, self.spinbtn_day, day_max)
            day_spinbtn.connect("wrapped", self.on_day_spinbtn_wrapped, self.spinbtn_month)
            month_spinbtn.connect("wrapped", self.on_month_spinbtn_wrapped, self.spinbtn_year)
            sleep_minute_spinbtn.connect("wrapped", self.on_sleep_minute_spinbtn_wrapped, self.spinbtn_sleep_hour)

            month_spinbtn.connect("value_changed",
                                  self.on_month_spinbtn_value_changed,
                                  self.spinbtn_year, self.spinbtn_day)
            year_spinbtn.connect("value_changed",
                                 self.on_year_spinbtn_value_changed,
                                 self.spinbtn_month, self.spinbtn_day)

    def get_unlock_status(self):
        if self.unlock:
            return True
        else:
            return False

    def on_unlockbtn_clicked(self, widget):
        self.unlock = True

    def on_advancebtn_clicked(self, widget):
        """ network advance option dialog """

        dia_advance = advance.Advance()
        dia_advance.run()

    def on_aboutbtn_clicked(self, widget):
        """ build about dialog and run """

        dia_about = aboutdialog.About(self.gladefile['aboutdialog'])
        dia_about.run()

    def on_sec_spinbtn_press(self, widget, date=None):
        """ when press second spinbutton the time will stop """

        self.time_value_changed = 1

    def on_minute_spinbtn_press(self, widget, date=None):
        """ when press minute spinbutton the time will stop """

        self.time_value_changed = 1

    def on_hour_spinbtn_press(self, widget, date=None):
        """ when press hour spinbutton the time will stop """

        self.time_value_changed = 1

    def on_sec_spinbtn_wrapped(self, widget, minute_spinbtn):
        """when the value of spinbtn wrapped, update it, and carry bit
        when the next bit out of upper, set 0.
        """

        widget.set_value(widget.get_value())
        value = minute_spinbtn.get_value() + 1.0
        minute_spinbtn.set_value(value)
        if int(value) == 60:
            minute_spinbtn.set_value(0.0)

    def on_minute_spinbtn_wrapped(self, widget, hour_spinbtn):
        """when the value of spinbtn wrapped, carry bit
        when the next bit out of upper, set 0.
        """

        value = hour_spinbtn.get_value() + 1.0
        hour_spinbtn.set_value(value)
        if int(value) == 24:
            hour_spinbtn.set_value(0.0)

    def on_hour_spinbtn_wrapped(self, widget, day_spinbtn, day_max):
        """when the value of spinbtn wrapped, carry bit
        when the next bit out of upper, set 1.
        """

        value = day_spinbtn.get_value() + 1.0
        day_spinbtn.set_value(value)
        if int(value) == int(day_max) + 1:
            day_spinbtn.set_value(1.0)

    def on_day_spinbtn_wrapped(self, widget, month_spinbtn):
        """when the value of spinbtn wrapped, carry bit
        when the next bit out of upper, set 1.
        """

        value = month_spinbtn.get_value() + 1.0
        month_spinbtn.set_value(value)
        if int(value) == 13:
            month_spinbtn.set_value(1.0)

    def on_month_spinbtn_wrapped(self, widget, year_spinbtn):
        """when the value of spinbtn wrapped, carry bit
        when the next bit out of upper, set 0.
        """

        value = year_spinbtn.get_value() + 1.0
        year_spinbtn.set_value(value)
        if int(value) == 3001:
            year_spinbtn.set_value(0.0)

    def on_month_spinbtn_value_changed(self, widget, year_spinbtn, day_spinbtn):
        """ different month have different days(and Run years) """

        year = year_spinbtn.get_value_as_int()
        month = widget.get_value_as_int()
        day = day_spinbtn.get_value()

        if month in [1, 3, 5, 7, 8, 10, 12]:
            day_max = 31.0
        elif month in [4, 6, 9, 11]:
            day_max = 30.0
        else:
            if ((year % 4 == 0) and (year % 100 != 0)) or (year % 400 == 0):
                day_max = 29.0
            else:
                day_max = 28.0

        day_adj = gtk.Adjustment(day, 1.0, day_max, 1.0, 10.0, 0.0)
        self.spinbtn_day.set_adjustment(day_adj)

    def on_year_spinbtn_value_changed(self, widget, month_spinbtn, day_spinbtn):
        """ different month have different days(and Run years) """

        month = month_spinbtn.get_value_as_int()
        year = widget.get_value_as_int()
        day = day_spinbtn.get_value()

        if month in [1, 3, 5, 7, 8, 10, 12]:
            day_max = 31.0
        elif month in [4, 6, 9, 11]:
            day_max = 30.0
        else:
            if ((year % 4 == 0) and (year % 100 != 0)) or (year % 400 == 0):
                day_max = 29.0
            else:
                day_max = 28.0

        day_adj = gtk.Adjustment(day, 1.0, day_max, 1.0, 10.0, 0.0)
        self.spinbtn_day.set_adjustment(day_adj)

    def on_sleep_minute_spinbtn_wrapped(self, widget, sleep_hour_spinbtn):
        """when the value of spinbtn wrapped, carry bit.
        when the next bit out of upper, set 0.
        """

        value = sleep_hour_spinbtn.get_value() + 1.0
        sleep_hour_spinbtn.set_value(value)
        if int(value) == 10:
            sleep_hour_spinbtn.set_value(0.0)

    def on_intercombobox_changed(self, widget, data=None):
        """when the interface name changed
           reset network
        """

        self.reload_network_setting()

    def reload_network_setting(self):
        # get interface name
        self.__cur_interface_name = self.combox_interface.get_active_text()
        self.__set_network_text()

    def on_wlancombobox_changed(self, widget, data=None):
        """when the wifi essid changed
           update
        """

        '''select_essid = self.combox_wlan.get_active_text()
        with open('/etc/wpa_supplicant.conf', 'r') as f:
            i = 0
            line = f.readlines()
            for li in line:
                if "\tssid=" in li:
                    line[i] = "\tssid=\"%s\"\n" % select_essid.strip('\n')
                    break
                i += 1
        with open('/etc/wpa_supplicant.conf', 'w') as f:
            f.writelines(line)
        '''
        pass

    def on_resolution_combobox_changed(self, widget, data=None):

        # get resolution value
        resolution_text = ''
        resolution_text = self.combox_resolution.get_active_text()
        for mode,info in resolution_dict.items():
            if resolution_text == info:
                self.resolution_val_new = mode
                break

    def __set_network_text(self):
        """  set network:  static ip or dhcp
        if static: set ip addr netmask gateway, dns
        """

        self.__nic_dict = bt.read_file(list(ifconfig.list_ifs()) + ['lo'])

        if self.__cur_interface_name in self.__nic_dict:
            info = self.__nic_dict[self.__cur_interface_name]
            if 'static' in info:
                self.rbtn_static.set_active(True)
                for x in info.split('\n'):
                    if 'address' in x:
                        self.entbuf_ip.set_text(x.replace('address', '').strip())
                    if 'netmask' in x:
                        self.entbuf_mask.set_text(x.replace('netmask', '').strip())
                    if 'gateway' in x:
                        self.entbuf_gateway.set_text(x.replace('gateway', '').strip())
                self.entbuf_dns.set_text(self.__dnsinfo.replace('nameserver', '').strip())
            else:
                self.rbtn_dhcp.set_active(True)
            self.rbtn_static.emit("toggled")

    def is_network_changed(self):
        """Judge whether the network configure changed.
        return True when changed.
        """

        if self.net_mode_changed:
            self.net_mode_changed = False
        #    return True

        if self.__cur_interface_name in self.__nic_dict:
            info = self.__nic_dict[self.__cur_interface_name]

            if info == '':
                return True

            if 'static' in info:
                if self.rbtn_static.get_active():
                    for x in info.split('\n'):
                        if 'address' in x:
                            if cmp(self.entbuf_ip.get_text().strip(), x.replace('address', '').strip()):
                                return True
                        if 'netmask' in x:
                            if cmp(self.entbuf_mask.get_text().strip(), x.replace('netmask', '').strip()):
                                return True
                        if 'gateway' in x:
                            if cmp(self.entbuf_gateway.get_text().strip(), x.replace('gateway', '').strip()):
                                return True
                    if cmp(self.entbuf_dns.get_text().strip(), self.__dnsinfo.replace('nameserver', '').strip()):
                        return True
                else:
                    return True
            elif 'dhcp' in info:
                if self.rbtn_static.get_active():
                    return True

        return False

    def save_server_config(self):
        proto = 'https'
        srvurl = self.entbuf_url.get_text().strip()
        # self.upgradeinfo_save(srvurl)
        self.baseUrl = '%s://%s:%s/ovirt-engine/api' % (proto, srvurl,
                                                        self.entbuf_port.get_text().strip())

        self.Password = self.entbuf_pwd.get_text().strip()

        username = self.entbuf_user.get_text().strip()
        passwd = bt.encrypt(self.__pwd_key, self.Password)
#        auto_login = str(self.cbtn_autologin.get_active())
#        store_pwd = str(self.cbtn_autologin.get_active())
        ent_name = self.entry_name.get_text().strip()
        ent_dname = self.entry_dname.get_text().strip()
        reguest = str(self.cbtn_reguest.get_active())
        scaling = str(self.cbtn_scaling.get_active())
        cbtn_wlan = str(self.cbtn_wlan.get_active())
        msg_data = (self.baseUrl, username, passwd,# auto_login,store_pwd,
                    ent_name, ent_dname, reguest, scaling,
                    cbtn_wlan, self.class_url_info)
        try:
            self.mutex_send.acquire()
            self.conn_send.send(('save_config', msg_data))
        finally:
            self.mutex_send.release()
        try:
            cmd = 'sudo ntpdate %s' % self.entbuf_url.get_text().strip()
            subprocess.Popen(cmd, shell=True)
            subprocess.Popen('sudo hwclock -w', shell=True)
        except:
            pass


    def set_net_config(self):
        """ set network config : ip, dns """

        ip_description = ''
        dns_description = ''
        # if static
        if self.rbtn_static.get_active():
            ipaddr = self.entbuf_ip.get_text().strip()
            netmask = self.entbuf_mask.get_text().strip()
            gateway = self.entbuf_gateway.get_text().strip()
            dnsserver = self.entbuf_dns.get_text().strip()
            # set ipaddr, netmask, gateway
            ipret, ip_description = bt.process_netconfig(self.__cur_interface_name,
                                                         False,
                                                         ipaddr,
                                                         netmask,
                                                         gateway)
            if not ipret:
                log.error("process netconfig failed! %s", ip_description)

            # set dns
            if dnsserver:
                dnsret, dns_description = bt.process_dnsconfig(dnsserver)
                if not dnsret:
                    log.error("process dnsconfig failed! %s", dns_description)
            else:
                dnsret, dns_description =  True, ''
        # dhcp
        else:
            ipret, ip_description = bt.process_netconfig(self.__cur_interface_name, True)
            dnsret = True
            dns_description = ''

        if ipret and dnsret:
            self.__nic_dict[self.__cur_interface_name] = ip_description
            return True, ''
        if ipret and not dnsret:
            return False, dns_description
        else:
            return False, ip_description + dns_description

    def run(self):
        try:
            result = self.dia_setting.run()
  #          autologin = self.cbtn_autologin.get_active()
        except:
            return result#, autologin
        return result#, autologin

    def on_dialog_destroy(self, widget):
        ifconfig.shutdown()
        self.dia_setting.destroy()

    def on_cancel_btn_clicked(self, widget, date=None):
        self.dia_setting.response(gtk.RESPONSE_CANCEL)
        self.dia_setting.destroy()

    def on_key_press(self, widget, event):
        """key press event
        """

        key = gtk.gdk.keyval_name(event.keyval)
        if 'Escape' == key:
            self.btn_cancel.emit('clicked')
        if 'Return' == key or 'KP_Enter' == key:
            self.btn_ok.emit('clicked')

    def on_settingdialog_delete_event(self, widget, event):
        self.btn_cancel.emit('clicked')

    def on_conn_wlan_clicked(self, widget):
        wlanwin = wlandialog.Wlan(self.combox_wlan.get_active_text(), self.rbtn_dhcp.get_active())
        wlanwin.run()

    def on_okbtn_clicked(self, widget, data=None):
        """press OK, save config, set network config, set system setting
        if falled return False print error message
        """
        url = self.entbuf_teacher.get_text().strip()
        save_teacher_url(url)

        if self.teacher_flag:
            self.class_url_info = self.entbuf_class.get_text().strip()
        else:
            self.class_url_info = url


        errmsg = ''
        ret, info = self.checkargs()
        if ret:
            self.save_server_config()
        else:
            errmsg += info

        self.ServerIP = self.entbuf_url.get_text().strip()
        self.btn_upgrade_save.emit("clicked")

        is_network_changed = self.is_network_changed()
        if is_network_changed:
            ret, info = self.set_net_config()
            if ret:
                bt.config_ethernet(self.__nic_dict, self.entbuf_dns.get_text(), self.wlan_on)
            else:
                errmsg += info
        else:
            bt.write_dns(self.entbuf_dns.get_text())
        if errmsg:
            #errmsg += '  (配置错误! 将恢复默认)'
            msgdia_error = settingerrordialog.Error(errmsg)
            msgdia_error.run()
        else:
            self.set_system_time()
            time.sleep(1)
            self.dia_setting.destroy()

        self.dia_setting.response(gtk.RESPONSE_OK)

        # set resolution
        if self.resolution_val_old != self.resolution_val_new:
            with open(DISPMODE, 'r') as dispmode_info_file:
                dispmode_info = dispmode_info_file.readlines()
                line_num = -1
                for line in dispmode_info:
                    line_num += 1
                    if line.strip().startswith('setdispmode'):
                        dispmode_info[line_num] = 'setdispmode %d\n' % self.resolution_val_new
                        with open(DISPMODE, 'w') as dispmode_file:
                            dispmode_file.writelines(dispmode_info)
                self.cur_dispmode = self.combox_resolution.get_active_text()
                self.config.read('/var/ovirt.conf')
                try:
                    self.config.set('last_dispmode', 'last_dispmode', self.cur_dispmode)
                except:
                    with open("/var/ovirt.conf", 'a') as fp:
                        fp.write("\n[last_dispmode]\nlast_dispmode = " + self.cur_dispmode)
        	with open('/var/ovirt.conf', 'w') as f:
                    self.config.write(f)
            self.resolution_val_old = self.resolution_val_new
            try:
                cmd = 'sudo setdisplay.sh %d' % self.resolution_val_new
                subprocess.Popen(cmd, shell=True)
            except:
                log.info("ERROR")

        #if is_network_changed:
        #    subprocess.Popen("sudo /etc/init.d/networking restart", shell=True)

        #brightness_value = os.popen('cat %s' % BRIGHTNESS)
        #brightness_value = int(brightness_value.read())
        #cmd = 'echo %s > /var/brightness' % brightness_value
        #subprocess.Popen(cmd, shell=True)
            #try:
            #    self.server_conn_send.send(('poweroff', None))
            #except:
            #    pass
            #os.system("sudo reboot")

    def on_teacherbtn_clicked(self, widget, data=None):
        url = self.entbuf_teacher.get_text().strip()
        save_teacher_url(url)

        if self.teacher_flag:
            class_url_info = self.entbuf_class.get_text().strip()
            self.config.read("/var/ovirt.conf")
            self.config.set('Class', 'class_url', class_url_info)
            with open("/var/ovirt.conf", 'w') as f:
                self.config.write(f)

    def on_serverbtn_clicked(self, widget, data=None):
        """press save, save config
        if falled return False print error message
        """

        errmsg = ''
        ret, info = self.checkargs()
        if ret:
            self.save_server_config()
            self.ServerIP = self.entbuf_url.get_text().strip()
            self.btn_upgrade_save.emit("clicked")
        else:
            errmsg += info
        if errmsg:
            #errmsg += '  (配置错误! 将恢复默认)'
            msgdia_error = settingerrordialog.Error(errmsg)
            msgdia_error.run()

    def on_cbtn_screensleep_toggled(self, widget, data=None):

        if self.cbtn_screensaver.get_active():
            self.spinbtn_sleep_hour.set_sensitive(True)
            self.spinbtn_sleep_minute.set_sensitive(True)
        else:
            self.spinbtn_sleep_hour.set_sensitive(False)
            self.spinbtn_sleep_minute.set_sensitive(False)

    def set_system_time(self):
        """ set system time, sleep time and save sleep time,
        and turn on/off sleep mode, and select suspend or close screen
        """

        # get datetime
        year = int(self.spinbtn_year.get_value())
        month = int(self.spinbtn_month.get_value())
        day = int(self.spinbtn_day.get_value())
        hour = int(self.spinbtn_hour.get_value())
        minute = int(self.spinbtn_minute.get_value())
        sec = int(self.spinbtn_sec.get_value())
        sleep_hour = self.spinbtn_sleep_hour.get_value_as_int()
        sleep_minute = self.spinbtn_sleep_minute.get_value_as_int()

        # save sleep time
        with open(SLEEP_TIME) as sleep_time_file:
            lines = sleep_time_file.readlines()

            lines[4] = 'timeout:        %d:%02d:%02d\n' % (sleep_hour, sleep_minute, 0)
            with open(SLEEP_TIME, 'w') as sleep_time_file:
                sleep_time_file.writelines(lines)

        # set sleep mode from sleepcbtn
        with open(SLEEP_TIME) as sleep_time_file:
            lines = sleep_time_file.readlines()

        if self.cbtn_screensaver.get_active():
            lines[36] = 'mode:           blank\n'
        else:
            lines[36] = 'mode:           off\n'

        sleep_time_file = open(SLEEP_TIME, 'w')
        sleep_time_file.writelines(lines)
        sleep_time_file.close()
        subprocess.Popen('xscreensaver-command -restart', shell=True)
        # set datetime command str
        date_str = 'sudo date %02d%02d%02d%02d%04d.%02d' % (month, day, hour, minute, year, sec)
        # print date_str
        subprocess.Popen(date_str, shell=True)
        subprocess.Popen('sudo hwclock -w', shell=True)

    def on_upgradebtn_clicked(self, widget, data=None):
        errmsg = ''
        self.upgrade_addr = self.entbuf_upgrade.get_text().strip()

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
                if ':' in self.upgrade_addr:
                    upgrade_info[server_line] = 'http://%s\n' % (self.upgrade_addr)
                else:
                    upgrade_info[server_line] = 'http://%s:8000\n' % self.upgrade_addr
                file_write.writelines(upgrade_info)


    def on_wlan_toggled(self, widget, data=None):
        self.net_mode_changed = True
        self.__nic_dict = bt.read_file(list(ifconfig.list_ifs()) + ['lo'])
        if widget.get_active():
            self.enable_wlan()
        else:
            self.disable_wlan()
        self.config_net_ipinfo()

    def config_net_ipinfo(self):
        curif = ifconfig.find_if_by_name(self.__cur_interface_name)
        if curif.is_up() and ip_format_check(curif.get_ip()):
            return

        ret, info = self.set_net_config()
        if ret:
            bt.config_ethernet(self.__nic_dict, self.entbuf_dns.get_text(), self.wlan_on)

    def checkargs(self):
        """ check settingdialog if something empty"""

        info = ''
        ret = True
        if not self.entbuf_url.get_text().strip():
            info = '服务器地址不能为空'
            log.error("server address can not be empty when config")
            ret = False
        if not self.entbuf_port.get_text().strip():
            info = '端口号不能为空'
            log.error("server port can not be empty when config")
            ret = False
        return ret, info

    def on_settingnotebook_switch_page(self, notebook, page, pagenum):
        """ if not set time page remove time_update """

        if (2 == pagenum):
            #with open(SLEEP_TIME) as sleep_time_file:
            #    lines = sleep_time_file.readlines()

            if self.cbtn_screensaver.get_active():
                self.spinbtn_sleep_hour.set_sensitive(True)
                self.spinbtn_sleep_minute.set_sensitive(True)
            #    lines[36] = 'mode:           blank\n'
            else:
                self.spinbtn_sleep_hour.set_sensitive(False)
                self.spinbtn_sleep_minute.set_sensitive(False)
            #    lines[36] = 'mode:           off\n'

            #sleep_time_file.close()
            self.time_update_id = gobject.timeout_add_seconds(1, self.time_update)
        else:
            self.time_value_changed = None
            if self.time_update_id:
                gobject.source_remove(self.time_update_id)
                self.time_update_id = None
        if (3 == pagenum):
            with open(UPGRADE_INFO, 'r') as upgrade_info_file:
                upgrade_info = upgrade_info_file.readlines()

                for line in upgrade_info:
                    if line.strip().startswith('mode:'):
                        mode = line.strip('mode:')
                        break

#n            else:
            self.entbuf_upgrade.set_sensitive(True)
            upgrade_server = upgrade_info[4].strip()
                #p1 = upgrade_server.index('/')
                #p2 = upgrade_server[p1+2:].index('/')
                #upgrade_server = upgrade_server[p1+2:p1+2+p2]
                #p3 = upgrade_server.index(':')
            p1 = upgrade_server.index('/')
            upgrade_server = upgrade_server[p1+2:]
            p2 = upgrade_server.index(':')
            if '8000' == upgrade_server[p2+1:].strip():
                self.entbuf_upgrade.set_text(upgrade_server[:p2].strip())
            else:
                self.entbuf_upgrade.set_text(upgrade_server.strip())
        if (4 == pagenum or 5 == pagenum):
            self.show_info()

    def time_update(self):
        """ refresh time every 1 seconds """

        if not self.time_value_changed:
            (_, _, _, hour, minute, sec, _, _, _) = time.localtime()
            self.spinbtn_hour.set_value(hour)
            self.spinbtn_minute.set_value(minute)
            self.spinbtn_sec.set_value(sec)

        return True

    def show_info(self):
        """ print 'host information update' """
        dns_num = 0
        dns_message = []
        if os.path.exists(DNS):
            with open(DNS, 'r') as dns_info_file:
                dns_info = dns_info_file.readlines()
                for line in dns_info:
                    if line.strip().startswith('nameserver'):
                        try:
                            dns_message.append(line.split()[1])
                        except:
                            pass
        text = gtk.TextBuffer()
        info = "\t系统信息:\n"
        info += '\tSN: %s\n\n' % getsn()
        info += '\t网络信息:\n'
        for iter_ in ifconfig.list_ifs():
            curif = ifconfig.find_if_by_name(iter_)
            info += '\t\t{0}: '.format(curif.name)
            info += '[%s]\n' % ('up' if curif.is_up() else 'down')
            if curif.is_up():
                _, netmask_str = curif.get_netmask()
                info += '\t\tip: {0}\n\t\tmac: {1}\n\t\tnetmask: {2}\n\n'.format(curif.get_ip(),
                                                                           curif.get_mac(),
                                                                           netmask_str)
            else:
                info += '\n'

        info += "\t\tdns: "
        for dns_item in dns_message:
            if not dns_num:
                info += '{0}\n'.format(dns_item)
                dns_num += 1
            else:
                info += '\t\t     {0}\n'.format(dns_item)
        text.set_text(info)
        self.txtview_info.set_buffer(text)

    def on_dhcpradiobtn_toggled(self, widget, data=None):
        """ set ip mask gateway dns  """

        if self.rbtn_dhcp.get_active():
            self.entbuf_ip.set_sensitive(False)
            self.entbuf_mask.set_sensitive(False)
            self.entbuf_gateway.set_sensitive(False)
            self.entbuf_dns.set_sensitive(False)
            self.entbuf_ip.set_text("")
            self.entbuf_mask.set_text("")
            self.entbuf_gateway.set_text("")
            self.entbuf_dns.set_text("")
        elif self.rbtn_static.get_active():
            self.entbuf_ip.set_sensitive(True)
            self.entbuf_mask.set_sensitive(True)
            self.entbuf_gateway.set_sensitive(True)
            self.entbuf_dns.set_sensitive(True)


def getsn():
    sn = ''

    if not os.path.isfile(IDPATH):
        return sn
    with open(IDPATH, 'r') as f:
        sn = f.readlines()

    return sn[0]

if "__main__" == __name__:
    pwdkey = 13
