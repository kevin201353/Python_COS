#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 ShenCloud Inc.
#

""" network advance setting """

import pygtk
pygtk.require('2.0')
import gtk
import sys
import os
import ConfigParser
import addhostdialog
import edithostdialog
import deletehost

IMAGEDIR = os.path.join(os.path.dirname(__file__), 'images')
HOSTDIR = "/etc/hosts"
# test HOSTDIR = "/etc/host"


def insert_treeview_from_list(treeview_hostinfo):
    """ read ipaddr and host name from file and write to treeview """

    treestore_hostinfo = gtk.TreeStore(str, str)  # tree model object

    # build ipaddr column
    cell_ipaddr = gtk.CellRendererText()
    treecolumn_ipaddr = gtk.TreeViewColumn()
    treecolumn_ipaddr.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
    treecolumn_ipaddr.set_fixed_width(160)
    treecolumn_ipaddr.set_title("IP地址")
    treecolumn_ipaddr.pack_start(cell_ipaddr, True)
    treecolumn_ipaddr.add_attribute(cell_ipaddr, "text", 0)
    treeview_hostinfo.append_column(treecolumn_ipaddr)

    # build host name column
    cell_host_name = gtk.CellRendererText()
    treecolumn_host_name = gtk.TreeViewColumn()
    treecolumn_host_name.set_title("主机名")
    treecolumn_host_name.pack_start(cell_host_name, True)
    treecolumn_host_name.add_attribute(cell_host_name, "text", 1)
    treeview_hostinfo.append_column(treecolumn_host_name)

    # read host information and write to treeview
    with open(HOSTDIR, 'r') as host_file:
        for host_info in host_file.readlines():
            if host_info.startswith('#') \
               or host_info.startswith('ff0') \
               or host_info.startswith('fe0') \
               or 'localhost' in host_info \
               or 'linaro-alip' in host_info:
                continue
            iter_hostinfo = treestore_hostinfo.append(None)
            host_list = host_info.split()
            if len(host_list) == 2:
                ipaddr, host_name = host_list[0], host_list[1]
            elif len(host_list) > 2:
                ipaddr, host_name = host_list[0], ' '.join(host_list[1:])
            else:
                continue
            treestore_hostinfo.set(iter_hostinfo, 0, ipaddr, 1, host_name)
        treeview_hostinfo.set_model(treestore_hostinfo)


class Advance(object):
    def __init__(self):
        self.selected_ipaddr = ''
        self.selected_host_name = ''
#        self.btn_ok = self.dia_advance.add_button("OK", gtk.RESPONSE_OK)
#        self.btn_cancel = self.dia_advance.add_button("Cancel", gtk.RESPONSE_CANCEL)
        self.config = ConfigParser.ConfigParser()
        self.config.read('/var/ovirt.conf')
        self.load_gladexml()
        self.btn_ok.connect("clicked", self.on_okbtn_clicked)
        self.btn_add.connect("clicked", self.on_addbtn_clicked)
        self.btn_edit.connect("clicked", self.on_editbtn_clicked)
        self.btn_delete.connect("clicked", self.on_deletebtn_clicked)
#        self.treeview_hostinfo.connect("selection-request-event", self.on_nothing_selected)

        self.dia_advance.set_title("")
        #Keep it stayed at the top of the parent window dialog, until closing
        self.dia_advance.set_modal(True)
        # self.dia_advance.set_decorated(False)

        # read ipaddr and host name from file and write to treeview
        insert_treeview_from_list(self.treeview_hostinfo)
        self.treeview_hostinfo.set_can_default(False)

        selection_hostinfo = self.treeview_hostinfo.get_selection()
        selection_hostinfo.connect("changed", self.on_selected_changed)
        selection_hostinfo.set_mode(gtk.SELECTION_SINGLE)
        self.selection_hostinfo = selection_hostinfo
        # get the selected host information
        treestore_hostinfo, treeiter_hostinfo = selection_hostinfo.get_selected()
        # if nothing be selected, it don't work
        if treeiter_hostinfo:
            self.selected_ipaddr = treestore_hostinfo.get_value(treeiter_hostinfo, 0)
            self.selected_host_name = treestore_hostinfo.get_value(treeiter_hostinfo, 1)
        else:
            self.selected_ipaddr = ''
            self.selected_host_name = ''

    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            advance_name = self.config.get('Config', 'logo_name')
            arr = advance_name + "_advance.glade"
            self.builder.add_from_file(arr)
        except:
            self.error_message("Failed to load UI XML fle: advance.glade")
            sys.exit(1)

        self.builder.connect_signals(self)
        self.dia_advance = self.builder.get_object("dia_advance")
        self.treeview_hostinfo = self.builder.get_object("treeview_hostinfo")
        self.btn_add = self.builder.get_object("btn_add")
        self.btn_edit = self.builder.get_object("btn_edit")
        self.btn_delete = self.builder.get_object("btn_delete")
        self.btn_ok = self.builder.get_object("btn_ok")

    def on_addbtn_clicked(self, widget):
        """ build add dialog and run"""

        add_host = addhostdialog.AddHost(self.treeview_hostinfo)
        add_host.run()

#    def on_nothing_selected(self, widget, date = None):
#        """ When nothing selected, set hostinfo empty """
#
#        print 'nothing be selected'
#        self.selected_ipaddr = ''
#        self.selected_host_name = ''
#        self.selection_hostinfo.unselect_all()
#
    def on_selected_changed(self, widget):
        """ When the selected changed, the information changed
        and if nothing selected, and edit button not work
        """
        treestore_hostinfo, treeiter_hostinfo = widget.get_selected()
        if treeiter_hostinfo:
            self.selected_ipaddr = treestore_hostinfo.get_value(treeiter_hostinfo, 0)
            self.selected_host_name = treestore_hostinfo.get_value(treeiter_hostinfo, 1)
        else:
            self.selected_ipaddr = ''
            self.selected_host_name = ''

    def on_editbtn_clicked(self, widget):
        """ build edit dialog and run"""

        # if nothing be selected, it don't work
        if not self.selected_ipaddr and not self.selected_host_name:
            pass
        else:
            _, treeiter_hostinfo = self.selection_hostinfo.get_selected()
            edit_host = edithostdialog.EditHost(self.treeview_hostinfo,
                                                self.selected_ipaddr,
                                                self.selected_host_name,
                                                treeiter_hostinfo)
            self.selected_ipaddr, self.selected_host_name = edit_host.run()

    def on_deletebtn_clicked(self, widget):
        """ delete the host information in the treeview """

        _, treeiter_hostinfo = self.selection_hostinfo.get_selected()
        if not treeiter_hostinfo:
            pass
        else:
            dummy_delete_host = deletehost.DeleteHost(self.treeview_hostinfo, treeiter_hostinfo)

    def on_okbtn_clicked(self, widget):
        """ write new host information in treeview to file"""

        with open(HOSTDIR, 'r') as host_file:
            read_hostinfo = host_file.readlines()

        with open(HOSTDIR, 'w') as host_file:
            # if it's localhost write it to file
            for line_info in read_hostinfo:
                if line_info.startswith('#') \
                   or line_info.startswith('ff0') \
                   or line_info.startswith('fe0') \
                   or 'localhost' in line_info \
                   or 'linaro-alip' in line_info:
                    host_file.writelines(line_info)

            # write the information which in the treeview to the file
            treestore_hostinfo = self.treeview_hostinfo.get_model()
            iter_hostinfo = treestore_hostinfo.get_iter_root()
            while iter_hostinfo:
                str_ipaddr = treestore_hostinfo.get_value(iter_hostinfo, 0)
                str_host_name = treestore_hostinfo.get_value(iter_hostinfo, 1)
                iter_hostinfo = treestore_hostinfo.iter_next(iter_hostinfo)
                host_file.writelines(str_ipaddr + '\t' + str_host_name + '\n')

    def run(self):
        self.dia_advance.run()
        self.dia_advance.destroy()

    def on_dia_advance_destroy(self, widget):
        self.dialog.destroy()
