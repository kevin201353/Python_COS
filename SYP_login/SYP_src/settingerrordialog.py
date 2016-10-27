#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 ShenCloud Inc.
#

""" setting error dialog """

import pygtk
pygtk.require('2.0')
import gtk
import sys


class Error(object):
    def __init__(self, errmsg):
        self.load_gladexml()

        #Keep it stayed at the top of the parent window dialog, until closing
        self.msgdia_error.set_modal(True)
        self.msgdia_error.set_title("")
        self.lbl_errmsg.set_text(errmsg)
        self.btn_ok.connect("clicked", self.on_error_msgdia_destroy)

    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file("settingerrordialog.glade")
        except:
            self.error_message("Failed to load UI XML fle: settingerrordialog.glade")
            sys.exit(1)

        self.builder.connect_signals(self)
        self.msgdia_error = self.builder.get_object("msgdia_error")
        self.btn_ok = self.builder.get_object("btn_ok")
        self.lbl_errmsg = self.builder.get_object("lbl_errmsg")

    def run(self):
        self.msgdia_error.run()
        self.msgdia_error.destroy()

    def on_error_msgdia_destroy(self, widget):
        self.msgdia_error.destroy()

if "__main__" == __name__:
    app = Error('wrong setting')
    gtk.main()
