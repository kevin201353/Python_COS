#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 ShenCloud Inc.
#

""" edit host name and ip address"""

import pygtk
pygtk.require('2.0')
import gtk
from gobject import GObject
import sys
import logging

log = logging.getLogger(__name__)


class EditHost(GObject):
    def __init__(self, treeview_hostinfo, selected_ipaddr, selected_host_name, treeiter_hostinfo):
        self.__gobject_init__()
        self.treeview_hostinfo = treeview_hostinfo
        self.selected_ipaddr = selected_ipaddr
        self.selected_host_name = selected_host_name
        self.treeiter_hostinfo = treeiter_hostinfo
        self.load_gladexml()
        self.btn_ok = self.dia_edit_host.add_button("确定", gtk.RESPONSE_OK)
        self.btn_cancel = self.dia_edit_host.add_button("取消", gtk.RESPONSE_CANCEL)

        # Keep it stayed at the top of the parent window dialog, until closing
        self.dia_edit_host.set_modal(True)
        self.dia_edit_host.set_title("编辑主机")

        self.entbuf_edit_ip.set_text(self.selected_ipaddr)
        self.entbuf_edit_host.set_text(self.selected_host_name)

        self.btn_ok.connect("clicked", self.on_okbtn_clicked)

    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file("edithostdialog.glade")
        except:
            log.error("Failed to load UI XML fle: edithostdialog.glade")
            sys.exit(1)

        self.builder.connect_signals(self)
        self.dia_edit_host = self.builder.get_object("dia_edit_host")
        self.entbuf_edit_ip = self.builder.get_object("entbuf_edit_ip")
        self.entbuf_edit_host = self.builder.get_object("entbuf_edit_host")

    def on_okbtn_clicked(self, widget):
        """get the information from user edit
        and write to treeview
        """

        str_ipaddr = self.entbuf_edit_ip.get_text()
        str_host_name = self.entbuf_edit_host.get_text()
        if not str_ipaddr or not str_host_name:
            str_err = 'IP地址或主机名不能为空！'
            errordlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, str_err)
            errordlg.set_title("")
            btn_ok = errordlg.get_widget_for_response(gtk.RESPONSE_OK)
            btn_ok.set_label("确定")
            logo_name = self.config.get('Config', 'logo_name')
            arr = self.config.get(logo_name, 'IMG_BANNER1')
            pixbuf = gtk.gdk.pixbuf_new_from_file(arr)
            errordlg.set_icon(pixbuf)

            errordlg.run()
            errordlg.destroy()
        else:
            treestore_hostinfo = self.treeview_hostinfo.get_model()
            treestore_hostinfo.set(self.treeiter_hostinfo,
                                   0, str_ipaddr,
                                   1, str_host_name)
            self.selected_ipaddr = str_ipaddr
            self.selected_host_name = str_host_name
            self.treeview_hostinfo.set_model(treestore_hostinfo)

    def run(self):
        self.dia_edit_host.run()
        self.dia_edit_host.destroy()
        return self.selected_ipaddr, self.selected_host_name

    def on_dia_edit_host_destroy(self, widget):
        self.dia_edit_host.destroy()
