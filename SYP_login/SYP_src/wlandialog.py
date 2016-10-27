#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 ShenCloud Inc.

import pygtk
pygtk.require('2.0')
import gtk
import ConfigParser
import os
import gobject
import checknetdialog
import subprocess
import gobject

WLAN_CMD = """sudo killall wpa_supplicant > /dev/null 2>&1
sudo wpa_supplicant -B -Dwext -iwlan0 -c/etc/wpa_supplicant.conf > /dev/null 2>&1"""
WPA_WAY = "/etc/wpa_supplicant.conf"
WLAN_CARR = "cat /sys/class/net/wlan0/carrier"
WLAN_CONN_TIMES = 10

def read_wlan_essid_and_passwd():
    essid, passwd = '', ''
    with open(WPA_WAY, 'r') as f:
        info = f.readlines()
        for line in info:
            if line.strip().startswith('ssid='):
                try:
                    essid = line.split('=')[1].strip().strip('"\n')
                except Exception, err:
                    pass
            if line.strip().startswith('psk='):
                try:
                    passwd = line.split('=')[1].strip().strip('"\n')
                except Exception, err:
                    pass
            if essid and passwd:
                break

    return essid, passwd

class Wlan(object):

    def __init__(self, wlan_essid, dhcp=True):
        self.wlan_essid = wlan_essid
        self.dhcp = dhcp
        self.wlan_conn_times = 0
        self.load_gladexml()
        self.btn_conn.connect("clicked", self.on_conn_wlan)
        self.btn_exit.connect("clicked", self.wlan_destroy)
        #self.dia_wlan.show()
        self.dia_wlan.set_title("")
        self.dia_wlan.set_modal(True)
        self.auto_conn_wlan()

    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file("wlandialog.glade")
        except:
            log.error("Failed to load UI XML file: wlandialog.glade")
            sys.exit(1)
        #self.builder.connect_signals(self)
        self.dia_wlan = self.builder.get_object("wlan_win")
        #self.dia_wlan.set_decorated(gtk.gdk.DECOR_BORDER)
        self.btn_conn = self.builder.get_object("btn_conn")
        self.btn_exit = self.builder.get_object("btn_exit")
        self.lab_wlan = self.builder.get_object("lab_wlan")
        self.ent_wlan = self.builder.get_object("ent_wlan")

    def auto_conn_wlan(self):
        essid, passwd = read_wlan_essid_and_passwd()
        if essid == self.wlan_essid and passwd:
            self.ent_wlan.set_text(passwd)
            #self.btn_conn.emit("clicked")

    def on_conn_wlan(self, widget):
        wlan_pwd = self.ent_wlan.get_text().strip('\n')
        if not wlan_pwd:
             self.lab_wlan.set_text("密码不能为空！")
             return

        with open(WPA_WAY, 'r') as f:
            i = 0
            line = f.readlines()
            for li in line:
                if "\tssid=" in li:
                    line[i] = "\tssid=\"%s\"\n" % self.wlan_essid
                if "\tpsk=" in li:
                    line[i] = "\tpsk=\"%s\"\n" % wlan_pwd
                i += 1
        with open(WPA_WAY, 'w') as f:
            f.writelines(line)
        self.btn_exit.emit("clicked")
        subprocess.Popen(WLAN_CMD, shell=True)
        gobject.timeout_add_seconds(3, self.wlan_conn_msg)
        self.network_dialog = checknetdialog.CheckNet()
        self.network_dialog.lbl_msg.set_text("无线正在连接...请稍候")

    def get_dhcp_ip(self):
        if_name = 'wlan0'
        subprocess.Popen("sudo kill `ps aux | grep dhclient | grep %s | grep -v grep | awk '{print $2}'` > /dev/null 2>&1" % if_name,
              shell=True)
        subprocess.Popen("sudo route del default", shell=True)
        subprocess.Popen("sudo ifconfig %s 0.0.0.0" % if_name, shell=True)
        subprocess.Popen("sudo dhclient %s > /dev/null 2>&1" % if_name, shell=True)
        return False

    def wlan_conn_msg(self):
        self.wlan_conn_times += 1
        #with open(WLAN_CARR, 'r') as f:
        try:
            val = subprocess.check_output(WLAN_CARR, shell=True)
        except Exception, err:
            return True
        li = val.strip('\n').strip()
        if li == '1':
            self.wlan_conn_times = 0
            self.network_dialog.lbl_msg.set_text("无线连接成功")
            self.network_dialog.btn_cancel = self.network_dialog.dialog.add_button("确定", gtk.RESPONSE_CANCEL)
            self.network_dialog.btn_cancel.connect("clicked", self.on_network_distroy)
            gobject.timeout_add_seconds(1, self.set_network_distroy)
            if self.dhcp:
                gobject.timeout_add_seconds(1, self.get_dhcp_ip)
            return False
        elif self.wlan_conn_times >= WLAN_CONN_TIMES:
            self.network_dialog.lbl_msg.set_text("无线连接失败, 请检查密码是否正确！")
            self.network_dialog.btn_cancel = self.network_dialog.dialog.add_button("确定", gtk.RESPONSE_CANCEL)
            self.network_dialog.btn_cancel.connect("clicked", self.on_network_distroy)
            return False
        return True

    def set_network_distroy(self):
        self.network_dialog.btn_cancel.emit("clicked")
        return False

    def on_network_distroy(self, widget):
        self.network_dialog.dialog.destroy()

    def wlan_destroy(self, widget):
        self.dia_wlan.destroy()
        return False

    def run(self):
        self.dia_wlan.run()
