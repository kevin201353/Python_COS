#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 ShenCloud Inc.

# -*- coding:utf-8-*-

"""login window module"""

import pygtk
pygtk.require('2.0')
import gtk
import os
import sys
import logging
import OVirtDispatcher
import basictools as bt
import ConfigParser
from cusdialog import DialogWith2Button
IMAGEDIR = os.path.join(os.path.dirname(__file__), 'images')
LOGINLOGO = os.path.join(IMAGEDIR, 'gf_login_ui.png')
#IMG = 'images/login_logo.png'


log = logging.getLogger(__name__)


class LoginWindow(object):
    """Initialize login window components
    define methods used to login window operation
    """

    def __init__(self, pwdkey, conn_send, conn_recv, mutex_send, mutex_recv):
        """1. Initialize login window components
        2. get status of autologin and storepwd from ovirt.conf, set their status
        """
        self.config = ConfigParser.ConfigParser()
        self.config.read('/var/ovirt.conf')
        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file("loginwindow.glade")
        except:
            log.error("Failed to load UI XML fle: loginwindow.glade")
            sys.exit(1)

        self.__pwdkey = pwdkey
        self.conn_send = conn_send
        self.conn_recv = conn_recv
        self.mutex_send = mutex_send
        self.mutex_recv = mutex_recv

        self.win = self.builder.get_object("window")
        self.entbuf_user = self.builder.get_object("userentry")
        self.entbuf_pwd = self.builder.get_object("pwdentry")
        self.btn_login = self.builder.get_object("loginbutton")
        self.lbl_warn = self.builder.get_object("warnlabel")
        #self.btn_quit = self.builder.get_object("quitbutton")
        self.btn_off = self.builder.get_object("offbutton")
        self.btn_manage = self.builder.get_object("managebutton")
        self.cbtn_autologin = self.builder.get_object("autologinchkbtn")
        self.cbtn_storepwd = self.builder.get_object("storepwdchkbtn")
        self.hbox_middle = self.builder.get_object("middlehbox")
        self.vbox = self.builder.get_object("vbox2")

        # the entbuf_user widget data source
        self.liststore = gtk.ListStore(str, str)
        cell = gtk.CellRendererText()
        self.entbuf_user.pack_start(cell)
        self.entbuf_user.add_attribute(cell, 'text', 1)
        self.entbuf_user.set_text_column(0)

        try:
            self.mutex_send.acquire()
            self.conn_send.send(('login_conf', None))
        finally:
            self.mutex_send.release()
        try:
            self.mutex_recv.acquire()
            msg_type, msg_data = self.conn_recv.recv()
        finally:
            self.mutex_recv.release()

        log.info("Recv msg: %s,%s" % (msg_type, msg_data))
        if msg_type == 'login_conf' and msg_data:
            (autoLogin, restorepwd, defuser, defpwd, self.user_list) = msg_data
            # add by zhanglu
            # add the data source to the ComboBoxEntry(self.entbuf_user: store the history user)
            if self.user_list:
                self.entbuf_user.child.set_text(defuser)
                if (autoLogin):
                    self.cbtn_autologin.set_active(True)
                if (restorepwd):
                    self.cbtn_storepwd.set_active(True)
                    self.entbuf_pwd.set_text(bt.decrypt(self.__pwdkey, defpwd))
                for user in self.user_list:
                    self.liststore.append([user["username"], ""])
                self.liststore.append(["--- 删除所有账户 ---", ""])
            self.entbuf_user.set_model(self.liststore)
            self.entbuf_user.connect('changed', self.on_user_changed)

        self.builder.connect_signals(self)

        # If user input text buffer is not empty, then lock the input
        if self.check_user_empty():
            self.on_user_unlock(True)
        else:
            self.on_user_unlock(False)

        width = gtk.gdk.Screen().get_width()
        height = gtk.gdk.Screen().get_height()
        self.win.set_size_request(width, height)

        self.pixbuf2 = None
        self.pixbuf1 = None
        self.win.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(red=12850, green=12850, blue=12850))
        #self.pixbuf = gtk.gdk.pixbuf_new_from_file(LOGINLOGO)
        #curwidth, curheight = self.win.get_size()
        #self.pixbuf = self.pixbuf.scale_simple(curwidth, curheight, gtk.gdk.INTERP_HYPER)

    def show(self):
        user = self.entbuf_user.child.get_text()
        if not user.startswith(("tec-", "tec_", "teacher")):
            self.btn_manage.hide()
        self.win.set_focus(self.btn_login)
        self.win.show()
        self.win.fullscreen()

    def check_user_empty(self):
        user = self.entbuf_user.child.get_text()
        passwd = self.entbuf_pwd.get_text()
        if len(user) == 0 or len(passwd) == 0:
            return True
        else:
            return False

    def on_user_unlock(self, stat):
        self.entbuf_user.set_sensitive(stat)
        self.entbuf_pwd.set_sensitive(stat)
        self.cbtn_storepwd.set_sensitive(stat)
        self.cbtn_autologin.set_sensitive(stat)

    def on_userpwd_changed(self, widget, data=None):
        """useless"""

        self.lbl_warn.set_text('')

    def on_user_changed(self, widget, data=None):
        """登录框账号的改变会触发下面密码框的数据变化"""
        password = ""
        username = self.entbuf_user.child.get_text()
        if username == "--- 删除所有账户 ---":
            self.delete_dialog = DialogWith2Button()  # delete all users dialog
            self.entbuf_user.child.set_text("")
            self.delete_dialog.set_cancelbtn_label("取消")
            self.delete_dialog.set_label_text("确定删除所有账户信息？")
            ret = self.delete_dialog.run()
            if ret:  # user ensure delete all history users
                with open("/var/users.conf", "w") as f:
                    f.truncate()
                self.liststore.clear()
                self.user_list = []
                self.config.set("oVirt", "username", "")
                self.config.set("oVirt", "password", "")
                with open("/var/ovirt.conf", 'w') as f:
                    self.config.write(f)
        else:
            if self.user_list:
                for user in self.user_list:
                    if user["username"] == username:
                        password = user["password"]

        self.entbuf_pwd.set_text(bt.decrypt(self.__pwdkey, password))

    def on_cbtn_autologin_toggled(self, widget, data=None):
        """autologin operation"""

        if self.cbtn_autologin.get_active():
            self.cbtn_storepwd.set_active(True)
            toggled = True
        else:
            toggled = False

        try:
            self.mutex_send.acquire()
            self.conn_send.send(('check_autologin', (toggled,)))
        finally:
            self.mutex_send.release()

    def on_cbtn_storepwd_toggled(self, widget, data=None):
        """storepwd operation"""

        if self.cbtn_storepwd.get_active():
            toggled = True
        else:
            self.cbtn_autologin.set_active(False)
            toggled = False

        try:
            self.mutex_send.acquire()
            self.conn_send.send(('check_storepwd', (toggled,)))
        finally:
            self.mutex_send.release()

    def on_window_show(self, widget, data=None):
        """useless"""

        if not self.cbtn_storepwd.get_active():
            self.entbuf_pwd.set_text('')

    def expose(self, widget, ev):
        """show interface"""

        #if not self.pixbuf:
        #    self.pixbuf = gtk.gdk.pixbuf_new_from_file(LOGINLOGO)
        #    curwidth, curheight = self.win.get_window().get_size()
        #    self.pixbuf = self.pixbuf.scale_simple(curwidth, curheight, gtk.gdk.INTERP_HYPER)
        #widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)
        return True

    def on_expose(self, widget, ev):
        """show interface"""

        if not self.pixbuf2:
            logo_name = self.config.get('Config', 'logo_name')
            str2 = self.config.get(logo_name, 'img_login_logo')
            self.pixbuf2 = gtk.gdk.pixbuf_new_from_file(str2)
            curwidth, curheight = self.hbox_middle.get_window().get_size()
            self.pixbuf2 = self.pixbuf2.scale_simple(curwidth, curheight, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf2, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)
        return True

    def login_expose(self, widget, ev):
        if not self.pixbuf1:
            logo_name = self.config.get('Config', 'logo_name')
            str1 = self.config.get(logo_name, 'img_login_logo_small')
            self.pixbuf1 = gtk.gdk.pixbuf_new_from_file(str1)
            curwidth_small,curheight_small = self.vbox.get_window().get_size()
            self.pixbuf1 = self.pixbuf1.scale_simple(curwidth_small, curheight_small, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf1, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)
        return True

def main():
    gtk.main()

if "__main__" == __name__:
    import ConfigParser
    pwdkey = 13
    config = ConfigParser.ConfigParser()
    config.read('/var/ovirt.conf')
    login = LoginWindow(pwdkey, config)
    main()
