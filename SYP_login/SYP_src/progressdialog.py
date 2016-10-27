#-*- coding:utf-8 -*-

import pygtk
pygtk.require('2.0')
import gtk
import logging

log = logging.getLogger(__name__)


class Refresh(object):
    def __init__(self, filename):
        self.filename = filename
        self.load_gladexml()
        self.dialog.set_modal(True)
        self.dialog.set_title("")

    def load_gladexml(self):
        try:
            self.builder = gtk.Builder()
            self.builder.add_from_file(self.filename)
        except Exception as e:
            log.info("load_gladexml failed: %s" % e)
            sys.exit(1)

        self.dialog = self.builder.get_object("dialog")
        self.lbl_vm = self.builder.get_object("lbl_vm")
        self.progressbar = self.builder.get_object("pbar")

    def run(self):
        result = self.dialog.run()
        self.dialog.destroy()
        return result

    def destroy(self):
        self.dialog.destroy()

    def response(self, signal):
        self.dialog.response(signal)

if "__main__" == __name__:
    app = Refresh()
    gtk.main()
