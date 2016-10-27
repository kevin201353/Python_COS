#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 ShenCloud Inc.
#

""" About version, log dialog"""

import pygtk
pygtk.require('2.0')
import gtk
import sys
import os
import logging

UPGRADE_INFO = '/var/upgrade.info'
SOFT_VERSION = '/var/SYP_login_version.info'

log = logging.getLogger(__name__)


class About(object):
    def __init__(self, gladefile):
        self.gladefile = gladefile
        self.load_gladexml()
        self.dia_about.set_title("")
        # Keep it stayed at the top of the parent window dialog, until closing
        self.dia_about.set_modal(True)
        self.btn_ok.connect("clicked", self.on_dia_about_destroy)
        self.upgrade_list = []


    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file(self.gladefile)
        except:
            log.error("Failed to load UI XML file: aboutdialog.glade")
            sys.exit(1)

        self.builder.connect_signals(self)
        self.dia_about = self.builder.get_object("dia_about")
        self.dia_about.set_decorated(gtk.gdk.DECOR_BORDER)
        self.lbl_software_info = self.builder.get_object("lbl_software_info")
        self.lbl_kernel = self.builder.get_object("lbl_kernel")
        self.btn_ok = self.builder.get_object("btn_ok")


    def run(self):
        with open(SOFT_VERSION, 'r') as soft_version_info_file:
            soft_version_info = soft_version_info_file.readlines()
            for info in soft_version_info:
                version_info = info.strip()
                version = version_info.split(':')[1].strip()

        output = os.popen('uname -a')
        output = output.read()
        output = output.strip('\n')
        p1 = output.index('#')
        p2 = output[p1:].index(' ')
        kernel_info = output[:p1+p2]
        self.lbl_software_info.set_text(version)
        self.lbl_kernel.set_text(kernel_info)

        self.dia_about.run()

    def on_dia_about_destroy(self, widget):
        self.dia_about.destroy()

if "__main__" == __name__:
    app = About()
    gtk.main()
