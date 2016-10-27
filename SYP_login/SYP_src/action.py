import os
import socket
from threading import Thread
from Queue import Queue

UNIXSOCKET = '/tmp/tcm.sock'

class ActionListener(object):
    def __init__(self, handler):
        self._handler = handler
        self._queue = Queue()
        self._clearSocket()
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._socket.bind(UNIXSOCKET)
        for func in [self._listener, self._processer]:
            self._thread = Thread(target=func)
            self._thread.setDaemon(True)
            self._thread.start()

    def _clearSocket(self):
        try:
            os.unlink(UNIXSOCKET)
        except Exception:
            pass

    def _listener(self):
        while True:
            data, _ = self._socket.recvfrom(16)
            self._queue.put(data)

    def _processer(self):
        while True:
            msg = self._queue.get(True)
            self._handler(msg)

class ActionSender(object):
    def __init__(self):
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    def send(self, data) :
        try:
            self._socket.sendto(data, UNIXSOCKET)
        except Exception:
            pass

