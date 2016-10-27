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


class PowerOff(object):
    def __init__(self):
        self.load_gladexml()

        # Keep it stayed at the top of the parent window dialog, until closing
        self.msgdia_poweroff.set_modal(True)
        self.msgdia_poweroff.set_title("")
        self.btn_ok.connect("clicked", self.on_okbtn_clicked)

    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file("startvmdialog.glade")
        except:
            log.error("Failed to load UI XML fle: startvmdialog.glade")
            sys.exit(1)

        self.builder.connect_signals(self)
        self.msgdia_poweroff = self.builder.get_object("messagedialog1")
        self.btn_ok = self.builder.get_object("btn_ok")
        self.btn_cancel = self.builder.get_object("btn_cancel")
        self.msgdia_poweroff.show()

    def on_okbtn_clicked(self, widget):
        self.msgdia_poweroff.response(gtk.RESPONSE_OK)

    def run(self):
        ret = self.msgdia_poweroff.run()
        self.msgdia_poweroff.destroy()
        if gtk.RESPONSE_OK == ret:
            self.msgdia_poweroff.destroy()
            return True
        else:
            return False

    def on_msgdia_poweroff_destroy(self, widget):
        self.msgdia_poweroff.destroy()
