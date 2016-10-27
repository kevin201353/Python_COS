#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 ShenCloud Inc.

# -*- coding:utf-8-*-

"main window module"

import pygtk
pygtk.require('2.0')
import gtk
import sys
import logging
import ConfigParser
import main


log = logging.getLogger(__name__)


class MainWindow(object):
    """Initialize lmain window components
    define methods used to main window operation
    """
    #self.config = ConfigParser.ConfigParser()
    #self.config.read('ovirt.conf')
    def __init__(self, identity_flag):
        self.identity_flag = identity_flag
        self.setting = ConfigParser.ConfigParser()
        self.setting.read('/root/.config/spicy/settings')
        self.config = ConfigParser.ConfigParser()
        self.config.read('/var/ovirt.conf')

        width = gtk.gdk.Screen().get_width()
        height = gtk.gdk.Screen().get_height()
        if width == 1368:
            self.section = "E_Class_Small"
        else:
            self.section = "E_Class"

        try:
            self.builder = gtk.Builder()
            if self.identity_flag == "teacher":
                if self.section == "E_Class_Small":
                    self.builder.add_from_file("mainwnd_tech_small.glade")
                else:
                    self.builder.add_from_file("mainwnd_tech.glade")
            elif self.identity_flag == "admin":
                self.builder.add_from_file("mainwnd_admin.glade")
        except:
            log.error("Failed to load UI XML fle: mainwnd.glade")
            sys.exit(1)

        if self.identity_flag == "teacher":
            settings = gtk.settings_get_default()
            settings.props.gtk_button_images = True
            self.win = self.builder.get_object("window")
            self.event_shangke = self.builder.get_object("eventbox2")
            self.event_xiake = self.builder.get_object("eventbox3")
            self.lbl_user = self.builder.get_object("userlabel")
            self.btn_off = self.builder.get_object("offbtn")
            self.btn_quit = self.builder.get_object("quitbtn")

        else:
            settings = gtk.settings_get_default()
            settings.props.gtk_button_images = True
            self.win = self.builder.get_object("window")
            self.treeview_machine = self.builder.get_object("machinetv")
            self.btn_quit = self.builder.get_object("quitbtn")
            self.btn_off = self.builder.get_object("offbtn")
            self.btn_refresh = self.builder.get_object("refreshbtn")
            self.tbl_top = self.builder.get_object("toptable")
            self.btn_start = self.builder.get_object("startbtn")
            self.btn_stop = self.builder.get_object("stopbtn")
            self.btn_about = self.builder.get_object("aboutbtn")
            self.btn_shutdown = self.builder.get_object("shutdownbtn")
            self.btn_conn = self.builder.get_object("connbtn")
            self.lbl_user = self.builder.get_object("userlabel")
            self.lbl_sum_vm = self.builder.get_object("vmsumlabel")
            self.lbl_curr_vm = self.builder.get_object("vmcurlabel")
            self.lbl_sum_vcpu = self.builder.get_object("vcpusumlabel")
            self.lbl_curr_vcpu = self.builder.get_object("vcpucurlabel")
            self.lbl_sum_vmem = self.builder.get_object("vmemsumlabel")
            self.lbl_curr_vmem = self.builder.get_object("vmemcurlabel")
            self.Progbar_vms = self.builder.get_object("vmspbar")
            self.Progbar_vcpu = self.builder.get_object("vcpupbar")
            self.Progbar_vmem = self.builder.get_object("vmempbar")
            self.liststore = self.builder.get_object("liststore")

        self.builder.connect_signals(self)
        self.pixbuf = None
        self.pixbuf1 = None
        self.pixbuf2 = None
        self.pixbuf3 = None
        self.pixbuf4 = None
        self.pixbuf5 = None
        self.pixbuf6 = None
        self.pixbuf7 = None
        self.pixbuf8 = None
        self.pixbuf9 = None

        self.win.set_size_request(width, height)
        self.win.fullscreen()
        self.win.show()

        if self.identity_flag == "teacher":
            str1 = self.config.get(self.section, 'img_big_logo')
            self.pixbuf1 = gtk.gdk.pixbuf_new_from_file(str1)
            curwidth, curheight = self.win.get_window().get_size()
            self.pixbuf1 = self.pixbuf1.scale_simple(curwidth, curheight, gtk.gdk.INTERP_HYPER)
            self.win.window.draw_pixbuf(self.win.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf1, 0, 0, 0, 0)

            change_user = self.config.get(self.section, "img_user_change")
            change_user_img = gtk.Image()
            change_user_img.set_from_file(change_user)
            change_user_img.show()
            self.btn_quit.add(change_user_img)


    def on_expose(self, widget, ev):
        """show interface"""
        # print '------mainwnd', ev, time.time()
        if not self.pixbuf:
            logo_name = self.config.get('Config', 'logo_name')
            arr = self.config.get(logo_name, 'img_banner')
            self.pixbuf = gtk.gdk.pixbuf_new_from_file(arr)
            curwidth, curheight = self.tbl_top.get_window().get_size()
            self.pixbuf = self.pixbuf.scale_simple(curwidth, curheight, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)
        # print '------expose', time.time()
        return True

    def on_expose_tech(self, widget, ev):
        """show interface"""

        if not self.pixbuf1:
            str1 = self.config.get(self.section, 'img_big_logo')
            self.pixbuf1 = gtk.gdk.pixbuf_new_from_file(str1)
            curwidth, curheight = self.win.get_window().get_size()
            self.pixbuf1 = self.pixbuf1.scale_simple(curwidth, curheight, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf1, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)
        return True

    def shangke_expose(self, widget, ev):
        if not self.pixbuf2:
            str2 = self.config.get(self.section, 'img_shangke')
            self.pixbuf2 = gtk.gdk.pixbuf_new_from_file(str2)
            curwidth_small,curheight_small = self.event_shangke.get_window().get_size()
            self.pixbuf2 = self.pixbuf2.scale_simple(curwidth_small, curheight_small, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf2, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)
        return True

    def shangke_enter_notify_event(self, widget, ev):
        if not self.pixbuf3:
            str3 = self.config.get(self.section, 'img_shangke_enter')
            self.pixbuf3 = gtk.gdk.pixbuf_new_from_file(str3)
            curwidth_small,curheight_small = self.event_shangke.get_window().get_size()
            self.pixbuf3 = self.pixbuf3.scale_simple(curwidth_small, curheight_small, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf3, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)
        return True

    def shangke_button_press_event(self, widget, ev):
        if not self.pixbuf4:
            str4 = self.config.get(self.section, 'img_shangke_click')
            self.pixbuf4 = gtk.gdk.pixbuf_new_from_file(str4)
            curwidth_small,curheight_small = self.event_shangke.get_window().get_size()
            self.pixbuf4 = self.pixbuf4.scale_simple(curwidth_small, curheight_small, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf4, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)

        self.config.read('/var/ovirt.conf')
        self.config.set('Class', 'shangke', True)
        with open('/var/ovirt.conf', 'w') as f:
            self.config.write(f)

        return True

    def xiake_expose(self, widget, ev):
        if not self.pixbuf6:
            str6 = self.config.get(self.section, 'img_xiake')
            self.pixbuf6 = gtk.gdk.pixbuf_new_from_file(str6)
            curwidth_small,curheight_small = self.event_xiake.get_window().get_size()
            self.pixbuf6 = self.pixbuf6.scale_simple(curwidth_small, curheight_small, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf6, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)

        return True

    def xiake_enter_notify_event(self, widget, ev):
        if not self.pixbuf7:
            str7 = self.config.get(self.section, 'img_xiake_enter')
            self.pixbuf7 = gtk.gdk.pixbuf_new_from_file(str7)
            curwidth_small,curheight_small = self.event_xiake.get_window().get_size()
            self.pixbuf7 = self.pixbuf7.scale_simple(curwidth_small, curheight_small, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf7, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)

        return True

    def xiake_button_press_event(self, widget, ev):
        if not self.pixbuf8:
            str8 = self.config.get(self.section, 'img_xiake_click')
            self.pixbuf8 = gtk.gdk.pixbuf_new_from_file(str8)
            curwidth_small,curheight_small = self.event_xiake.get_window().get_size()
            self.pixbuf8 = self.pixbuf8.scale_simple(curwidth_small, curheight_small, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf(widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf8, 0, 0, 0, 0)
        if widget.get_child():
            widget.propagate_expose(widget.get_child(), ev)

        self.config.read('/var/ovirt.conf')
        self.config.set('Class', 'xiake', True)
        with open('/var/ovirt.conf', 'w') as f:
            self.config.write(f)

        return True

    def shutdown_expose(self, widget, ev):
        shutdown_img = self.config.get(self.section, 'img_shutdown_leave')
        self.pixbuf_shutdown = gtk.gdk.pixbuf_new_from_file(shutdown_img)
        curwidth_small, curheight_small = self.btn_off.get_window().get_size()
        self.pixbuf_shutdown = self.pixbuf_shutdown.scale_simple(curwidth_small, curheight_small, gtk.gdk.INTERP_HYPER)
        widget.window.draw_pixbuf( widget.style.bg_gc[gtk.STATE_NORMAL], self.pixbuf_shutdown, 0, 0, 0, 0)

        return True


if "__main__" == __name__:
    mainwnd = MainWindow()
    gtk.main()
