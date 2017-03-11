#!/usr/bin/env python
# coding=utf-8
import time
import select


EV_READ = 1
EV_WRITE = 2


class IOLoop(object):
    MIN_INTERVAL = 0.05

    def __init__(self):
        self.rd_fds = {}    # fd -> callback
        self.wr_fds = {}
        self.err_callback = None
        self.timers = {}
        self.ts = 0

    def Register(self, fd, events, callback):
        if events & EV_READ:
            self.rd_fds[fd] = callback
        if events & EV_WRITE:
            self.wr_fds[fd] = callback
        return True

    def Unregister(self, fd):
        if fd in self.rd_fds:
            del self.rd_fds[fd]
        if fd in self.wr_fds:
            del self.wr_fds[fd]
        return True

    def SetErrCallback(self, callback):
        self.err_callback = callback
        return True

    def Run(self):
        pass

    def _CheckTimer(self):
        now = int(time.time())
        for callback, (seconds, next_ts) in self.timers.iteritems():
            if next_ts == now:
                callback()
                self.timers[callback][1] += seconds

    def SetTimer(self, seconds, callback):
        self.timers[callback] = [seconds, int(time.time()) + seconds]


class Select(IOLoop):
    def __init__(self):
        super(Select, self).__init__()
        self.rlist = []
        self.wlist = []
        self.elist = []

    def _make_list(self):
        self.rlist = self.rd_fds.keys()
        self.wlist = self.wr_fds.keys()
        s = set(self.rd_fds.keys() + self.wr_fds.keys())
        self.elist = [f for f in s]

    def Register(self, fd, events, callback):
        super(Select, self).Register(fd, events, callback)
        self._make_list()
        return True

    def Unregister(self, fd):
        super(Select, self).Unregister(fd)
        self._make_list()
        return True

    def Run(self):
        if len(self.rlist) == 0 and len(self.wlist) == 0:
            return
        while True:
            self._CheckTimer()
            (rl, wl, el) = select.select(self.rlist, self.wlist, self.elist,
                                         self.MIN_INTERVAL)
            for fd in rl:
                if fd in self.rd_fds:
                    self.rd_fds[fd](fd)
            for fd in wl:
                if fd in self.wr_fds:
                    self.wr_fds[fd](fd)
            if self.err_callback:
                for fd in el:
                    self.err_callback(fd)


class Epoll(IOLoop):
    def __init__(self):
        super(Epoll, self).__init__()
        self.epoll = select.epoll()

    def Register(self, fd, events, callback):
        ev = select.EPOLLERR | select.EPOLLHUP
        if events & EV_READ:
            ev |= select.EPOLLIN
        if events & EV_WRITE:
            ev |= select.EPOLLOUT
        try:
            self.epoll.register(fd, ev)
        except IOError:
            return False
        super(Epoll, self).Register(fd, events, callback)
        return True

    def Unregister(self, fd):
        super(Epoll, self).Unregister(fd)
        self.epoll.unregister(fd)
        return True

    def Run(self):
        while True:
            self._CheckTimer()
            events = self.epoll.poll(self.MIN_INTERVAL)
            for fd, event in events:
                if event & select.EPOLLERR or event & select.EPOLLHUP:
                    if self.err_callback:
                        self.err_callback(fd)
                elif event & select.EPOLLIN:
                    if fd in self.rd_fds:
                        self.rd_fds[fd](fd)
                elif event & select.EPOLLOUT:
                    if fd in self.wr_fds:
                        self.wr_fds[fd](fd)


def GetIOLoop(name="select"):
    if name == "epoll":
        return Epoll()
    elif name == "select":
        return Select()
    else:
        return None