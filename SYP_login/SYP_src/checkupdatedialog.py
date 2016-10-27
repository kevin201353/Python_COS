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


class CheckUpdate(object):
    def __init__(self):
        #self.load_gladexml()
        self.config = ConfigParser.ConfigParser()
        self.config.read('ovirt.conf')
        # Keep it stayed at the top of the parent window dialog, until closing
        self.load_gladexml()
        self.dialog.set_modal(True)
        self.dialog.set_title('')
   #     self.btn_ok.connect("clicked", self.on_dia_check_update_destroy)

    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            checkup_name = self.config.get('Config', 'logo_name')
            arr = checkup_name + "_checkupdatedialog.glade"
            self.builder.add_from_file(arr)

        except Exception, err:
            log.error("Failed to load UI XML fle: checkupdatedialog.glade")
            sys.exit(1)

    #    self.builder.connect_signals(self)
        self.dialog = self.builder.get_object("dialog_check_update")
        self.lbl_msg = self.builder.get_object("lbl_msg")

    def run(self):
        self.dialog.run()
        self.dialog.destroy()

    def on_dia_check_update_destroy(self, widget):
        self.dialog.destroy()
        
    def response(self, signal):
        self.dialog.response(signal)

if "__main__" == __name__:
    app = CheckUpdate()
    gtk.main()
