#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 ShenCloud Inc.

"""custom timer module"""

import inspect
import ctypes
import threading

class CustomTimer(object):
    """Custom loop timer

    when callback function return True, timer loop,
    otherwise timer stop"""

    def __init__(self, interval, function, args=[], kwargs={}):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def start(self):
        self.stop_flag = False
        self._timer = threading.Timer(self.interval, self._run)
        self._timer.setDaemon(True)
        self._timer.start()

    def stop(self):
        self.stop_flag = True
        if self.__dict__.has_key("_timer"):
            self._timer.cancel()
            del self._timer

    def _restart(self):
        self.stop()
        self.start()

    def _run(self):
        try:
            ret = self.function(*self.args, **self.kwargs)
        except:
            ret = True
        if ret:
            if self.stop_flag:
                pass
            else:
                self._restart()
        else:
            self.stop()

def _async_raise(tid, exctype):
    '''Raises an exception in the threads with id tid'''
    if not inspect.isclass(exctype):
        raise TypeError("Only types can be raised (not instances)")
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid,
                                                  ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # "if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)
        raise SystemError("PyThreadState_SetAsyncExc failed")

class StoppableThread(threading.Thread):
    def terminate(self):
        self.raiseExc(SystemExit)

    def raiseExc(self, exctype):
        """Raises the given exception type in the context of this thread.

        If the thread is busy in a system call (time.sleep(),
        socket.accept(), ...), the exception is simply ignored.

        If you are sure that your exception should terminate the thread,
        one way to ensure that it works is:

            t = ThreadWithExc( ... )
            ...
            t.raiseExc( SomeException )
            while t.isAlive():
                time.sleep( 0.1 )
                t.raiseExc( SomeException )

        If the exception is to be caught by the thread, you need a way to
        check that your thread has caught it.

        CAREFUL : this function is executed in the context of the
        caller thread, to raise an excpetion in the context of the
        thread represented by this instance.
        """
        _async_raise( self.ident, exctype )


