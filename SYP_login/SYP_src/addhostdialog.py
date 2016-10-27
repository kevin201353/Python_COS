#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 ShenCloud Inc.
#

""" add host name and ip address"""

import pygtk
pygtk.require('2.0')
import gtk
import sys
import logging

log = logging.getLogger(__name__)


class AddHost(object):
    def __init__(self, treeview_hostinfo):
        self.treeview_hostinfo = treeview_hostinfo
        self.load_gladexml()
        self.btn_ok = self.dia_add_host.add_button("确定", gtk.RESPONSE_OK)
        self.btn_cancel = self.dia_add_host.add_button("取消", gtk.RESPONSE_CANCEL)

        self.btn_ok.connect("clicked", self.on_okbtn_clicked)
        # Keep it stayed at the top of the parent window dialog, until closing
        self.dia_add_host.set_modal(True)
        self.dia_add_host.set_title("添加主机")

    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file("addhostdialog.glade")
        except:
            log.error("Failed to load UI XML fle: addhostdialog.glade")
            sys.exit(1)

        self.builder.connect_signals(self)
        self.dia_add_host = self.builder.get_object("dia_add_host")
        self.entbuf_ipaddr = self.builder.get_object("entbuf_ipaddr")
        self.entbuf_host_name = self.builder.get_object("entbuf_host_name")

    def on_okbtn_clicked(self, widget):
        """get the information from user input
        and write to treeview
        """

        str_ipaddr = self.entbuf_ipaddr.get_text()
        str_host_name = self.entbuf_host_name.get_text()
        if not str_ipaddr or not str_host_name:
            str_err = 'IP地址或主机名不能为空！'
            errordlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, str_err)
            errordlg.set_title("")
            btn_ok = errordlg.get_widget_for_response(gtk.RESPONSE_OK)
            btn_ok.set_label("确定")
            logo_name = self.config.get('Config', 'logo_name')
            arr = self.config.get(logo_name, 'img_banner1')
            pixbuf = gtk.gdk.pixbuf_new_from_file(arr)
            errordlg.set_icon(pixbuf)

            errordlg.run()
            errordlg.destroy()
        else:
            treestore_hostinfo = self.treeview_hostinfo.get_model()
            iter_hostinfo = treestore_hostinfo.append(None)
            treestore_hostinfo.set(iter_hostinfo, 0, str_ipaddr, 1, str_host_name)
            self.treeview_hostinfo.set_model(treestore_hostinfo)

    def run(self):
        self.dia_add_host.run()
        self.dia_add_host.destroy()

    def on_dia_add_host_destroy(self, widget):
        self.dia_add_host.destroy()
