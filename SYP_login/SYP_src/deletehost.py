#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 ShenCloud Inc.
#

""" delete host name and ip address"""


class DeleteHost(object):
    def __init__(self, treeview_hostinfo, treeiter_hostinfo):
        treestore_hostinfo = treeview_hostinfo.get_model()
        treestore_hostinfo.remove(treeiter_hostinfo)
        treeview_hostinfo.set_model(treestore_hostinfo)
