#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 ShenCloud Inc.
#

""" clicked poweroff button pop up dialog """

import pygtk
pygtk.require('2.0')
import gtk
import sys
import logging

log = logging.getLogger(__name__)


class DialogWith1Button(object):
    def __init__(self, glade_name="dialog_1button.glade",
                 btn1_label='确定', btn1_ret='OK'):

        self.load_gladexml(glade_name)

        # Keep it stayed at the top of the parent window dialog, until closing
        self.msg_dialog.set_modal(True)

        self.msg_dialog.set_title("")

        self.set_okbtn_label(btn1_label)
        if btn1_ret == 'OK':
            self.btn_ok.connect("clicked", self.on_okbtn_clicked_ok)
        else:
            self.btn_ok.connect("clicked", self.on_okbtn_clicked_cancel)

    def load_gladexml(self, glade_name):
        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file(glade_name)
        except:
            log.error("Failed to load UI XML fle: %s", glade_name)
            sys.exit(1)

        self.builder.connect_signals(self)
        self.msg_dialog = self.builder.get_object("messagedialog1")
        self.msg_label = self.builder.get_object("label1")
        self.btn_ok = self.builder.get_object("btn_ok")

    def set_okbtn_label(self, text):
        self.btn_ok.set_label(text)

    def set_label_text(self, text):
        self.msg_label.set_label(text)

    def on_okbtn_clicked_ok(self, widget):
        self.msg_dialog.response(gtk.RESPONSE_OK)

    def on_okbtn_clicked_cancel(self, widget):
        self.msg_dialog.response(gtk.RESPONSE_CANCEL)

    def run(self):
        ret = self.msg_dialog.run()
        self.msg_dialog.destroy()

        if gtk.RESPONSE_OK == ret:
            return True
        else:
            return False

    def on_msg_dialog_destroy(self, widget):
        self.msg_dialog.destroy()


class DialogWith2Button(DialogWith1Button):
    def __init__(self, glade_name="dialog_2button.glade",
                 btn1_label='确定', btn2_label='取消',
                 btn1_ret='OK', btn2_ret='CANCEL'):

        super(DialogWith2Button, self).__init__(glade_name, btn1_label, btn1_ret)

        self.btn_cancel = self.builder.get_object("btn_cancel")
        self.set_cancelbtn_label(btn2_label)
        if btn2_ret == 'OK':
            self.btn_cancel.connect("clicked", self.on_cancelbtn_clicked_ok)
        else:
            self.btn_cancel.connect("clicked", self.on_cancelbtn_clicked_cancel)

    def set_cancelbtn_label(self, text):
        self.btn_cancel.set_label(text)

    def on_cancelbtn_clicked_ok(self, widget):
        self.msg_dialog.response(gtk.RESPONSE_OK)

    def on_cancelbtn_clicked_cancel(self, widget):
        self.msg_dialog.response(gtk.RESPONSE_CANCEL)

