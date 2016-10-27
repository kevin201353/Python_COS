#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 ShenCloud Inc.

"""loginproess module"""

import gtk
import gobject
import time
import os
import threading
import subprocess
from threading import Thread
from subprocess import Popen
import select

import progressdialog
import upgradewindow
gobject.threads_init()

class DoUpgrade(object):
    def __init__(self):
        self.upgrade_percent = 0.1
        if os.path.exists('/tmp/upgrade_progress'):
            Popen("echo 0 > '/tmp/upgrade_progress'", shell=True)
        time.sleep(0.5)

    def client_do_upgrade(self):
        self.upgradewin = upgradewindow.UpgradeWindow()
        self.upgradewin.win.show()
        
        gobject.timeout_add(800, self.upgrade_progress)
        return False

    def upgrade_progress(self):
        self.upgradewin.progbar_upgrade.set_text('loading...')
        if os.path.exists('/tmp/upgrade_progress') == False:
            self.upgradewin.progbar_upgrade.pulse()
            self.upgradewin.progbar_upgrade.set_pulse_step(self.upgrade_percent)
        else:
            upgrade_progress = ''
            with open('/tmp/upgrade_progress', 'r') as upgrade_progress_file:
                upgrade_progress = upgrade_progress_file.read()
            upgrade_progress = float(upgrade_progress.strip('\n').strip())
            if upgrade_progress == 0:
                self.upgradewin.progbar_upgrade.pulse()
                self.upgradewin.progbar_upgrade.set_pulse_step(self.upgrade_percent)
                self.upgradewin.progbar_upgrade.set_text('loading...')
            else:
                self.upgrade_progress = upgrade_progress / 100
                self.upgradewin.progbar_upgrade.set_fraction(self.upgrade_progress)
                self.upgrade_progress = int(upgrade_progress)
                self.upgradewin.progbar_upgrade.set_text(str(self.upgrade_progress)+'%')
        self.upgrade_percent += 0.05
        if self.upgrade_percent >=0.15:
            self.upgrade_percent = 0.1
        return True

app = DoUpgrade()
app.client_do_upgrade()
#gobject.timeout_add_seconds(1, app.upgrade_progress)
gtk.main()
