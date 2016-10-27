#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 ShenCloud Inc.

# -*- coding:utf-8-*-

"""login window module"""

import pygtk
pygtk.require('2.0')
import gtk
import os

class UpgradeWindow(object):

    def __init__(self):

        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file("upgradewindow.glade")
        except:
            log.error("Failed to load UI XML fle: upgradewindow.glade")
            sys.exit(1)

        self.win = self.builder.get_object("window")
        self.progbar_upgrade = self.builder.get_object("progbar_upgrade")

        width = gtk.gdk.Screen().get_width()
        height = gtk.gdk.Screen().get_height()
        self.win.set_size_request(width, height)
        self.win.fullscreen()

        self.win.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(red=13107, green=26214, blue=52428))

def main():
    gtk.main()

if "__main__" == __name__:
    login = UpgradeWindow()
    main()
