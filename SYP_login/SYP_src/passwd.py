#!/usr/bin/env python
# coding: utf-8

import logging
import ConfigParser

import pygtk
pygtk.require('2.0')
import gtk

from cusdialog import DialogWith1Button

log = logging.getLogger(__name__)

class PasswdWindow(object):

    def __init__(self):
        self.validate = False
        self.load_gladexml()
        self.dialog.set_modal(True)
        self.dialog.set_title("")
        self.dialog.run()

    def load_gladexml(self):

        self.config = ConfigParser.ConfigParser()
        try:
            self.config.read('/var/ovirt.conf')
            self.passwd = self.config.get("oVirt", "adminpwd")
        except Exception:
            self.passwd = ''
        if len(self.passwd) == 0:
            self.passwd = "654123"

        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file("passwd.glade")
        except:
            return

        self.builder.connect_signals(self)
        self.dialog   = self.builder.get_object("dialog")
        self.pwdEty   = self.builder.get_object("pwdEty")
        self.okbtn    = self.builder.get_object("okbtn")
        self.canbtn   = self.builder.get_object("canbtn")

        self.okbtn.connect("clicked", self.on_chgpwd_clicked)
        self.canbtn.connect("clicked", self.destroy)
        self.dialog.connect("key-press-event", self.on_enter_press)

    def on_enter_press(self, widget, event):
        key = gtk.gdk.keyval_name(event.keyval)
        if 'Return' == key and self.dialog.is_active():
            self.okbtn.emit('clicked')

    def on_chgpwd_clicked(self, widget, data=None):
        pwd   = self.pwdEty.get_text()

        if not pwd:
            self.show('请输入密码！')
        else:
            if pwd == self.passwd:
                self.validate = True
                self.dialog.destroy()
            else:
                self.show('密码输入错误!')

    def is_validate(self):
        if self.validate:
            return True
        else:
            return False


    def show(self, info):
        dlg = DialogWith1Button(btn1_label='确定', btn1_ret='OK')
        dlg.set_label_text(info)
        dlg.run()

    def destroy(self, widget, data=None):
        self.dialog.destroy()

if __name__ == "__main__":
    PasswdWindow()
    gtk.main()

