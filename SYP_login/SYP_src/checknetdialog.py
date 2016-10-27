#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 ShenCloud Inc.
#

""" Check update dialog """

import pygtk
pygtk.require('2.0')
import gtk
import sys
import logging
import ConfigParser
log = logging.getLogger(__name__)

class CheckNet(object):
    def __init__(self):
        self.config = ConfigParser.ConfigParser()
        self.config.read('/var/ovirt.conf')
        self.load_gladexml()
        # Keep it stayed at the top of the parent window dialog, until closing
        self.dialog.set_modal(True)
        self.dialog.set_title('')
   #     self.btn_ok.connect("clicked", self.on_dia_check_update_destroy)

    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            checknet_name = self.config.get('Config', 'logo_name')
            arr = checknet_name + "_checknetdialog.glade"
            self.builder.add_from_file(arr)
        except:
            log.error("Failed to load UI XML fle: checknetdialog.glade")
            sys.exit(1)

    #    self.builder.connect_signals(self)
        self.dialog = self.builder.get_object("dialog_check_net")
        self.lbl_msg = self.builder.get_object("lbl_msg")

    def run(self):
        self.dialog.run()
        self.dialog.destroy()

    def on_dia_check_net_destroy(self, widget):
        self.dialog.destroy()

    def response(self, signal):
        self.dialog.response(signal)

if "__main__" == __name__:
    app = CheckNet()
    gtk.main()
