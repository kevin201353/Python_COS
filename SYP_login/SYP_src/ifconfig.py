#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 Shen Cloud, Inc.
#

"""
Config and get the configure info of the network interface

This file makes the following assumptions about data structures:

struct ifreq
{
    union
    {
        char    ifrn_name[16];
    } ifr_ifrn;

    union {
        struct    sockaddr ifru_addr;
        struct    sockaddr ifru_dstaddr;
        struct    sockaddr ifru_broadaddr;
        struct    sockaddr ifru_netmask;
        struct    sockaddr ifru_hwaddr;
        short     ifru_flags;
        int       ifru_ivalue;
        int       ifru_mtu;
        struct    ifmap ifru_map; // 16 bytes long
        char      ifru_slave[16];
        char      ifru_newname[16];
        void __user *    ifru_data;
        struct    if_settings ifru_settings;
    } ifr_ifru;
};

typedef unsigned short sa_family_t;

struct sockaddr {
    sa_family_t  sa_family;
    char         sa_data[14];
};

struct ifconf {
    int                 ifc_len; /* size of buffer */
    union {
        char           *ifc_buf; /* buffer address */
        struct ifreq   *ifc_req; /* array of structures */
    };
};


// From linux/ethtool.h

struct ethtool_cmd {
    __u32   cmd;
    __u32   supported;      /* Features this interface supports */
    __u32   advertising;    /* Features this interface advertises */
    __u16   speed;          /* The forced speed, 10Mb, 100Mb, gigabit */
    __u8    duplex;         /* Duplex, half or full */
    __u8    port;           /* Which connector port */
    __u8    phy_address;
    __u8    transceiver;    /* Which transceiver to use */
    __u8    autoneg;        /* Enable or disable autonegotiation */
    __u32   maxtxpkt;       /* Tx pkts before generating tx int */
    __u32   maxrxpkt;       /* Rx pkts before generating rx int */
    __u32   reserved[4];
};

struct ethtool_value {
    __u32    cmd;
    __u32    data;
};
"""

import fcntl
import os
import re
import socket
import struct
import ctypes
import array
import math
import logging
import ConfigParser
from subprocess import Popen, PIPE, call, CalledProcessError, STDOUT

log = logging.getLogger(__name__)


SYSFS_NET_PATH = "/sys/class/net"
PROCFS_NET_PATH = "/proc/net/dev"

# From linux/sockios.h
SIOCGIFCONF = 0x8912
SIOCGIFINDEX = 0x8933
SIOCGIFFLAGS = 0x8913
SIOCSIFFLAGS = 0x8914
SIOCGIFHWADDR = 0x8927
SIOCSIFHWADDR = 0x8924
SIOCGIFADDR = 0x8915
SIOCSIFADDR = 0x8916
SIOCGIFNETMASK = 0x891B
SIOCSIFNETMASK = 0x891C
SIOCETHTOOL = 0x8946

# From linux/if.h
IFF_UP = 0x1

# From linux/socket.h
AF_UNIX = 1
AF_INET = 2

# From linux/ethtool.h
ETHTOOL_GSET = 0x00000001  # Get settings
ETHTOOL_SSET = 0x00000002  # Set settings
ETHTOOL_GLINK = 0x0000000a  # Get link status (ethtool_value)
ETHTOOL_SPAUSEPARAM = 0x00000013  # Set pause parameters.

ADVERTISED_10baseT_Half = (1 << 0)
ADVERTISED_10baseT_Full = (1 << 1)
ADVERTISED_100baseT_Half = (1 << 2)
ADVERTISED_100baseT_Full = (1 << 3)
ADVERTISED_1000baseT_Half = (1 << 4)
ADVERTISED_1000baseT_Full = (1 << 5)
ADVERTISED_Autoneg = (1 << 6)
ADVERTISED_TP = (1 << 7)
ADVERTISED_AUI = (1 << 8)
ADVERTISED_MII = (1 << 9)
ADVERTISED_FIBRE = (1 << 10)
ADVERTISED_BNC = (1 << 11)
ADVERTISED_10000baseT_Full = (1 << 12)

# This is probably not cross-platform
SIZE_OF_IFREQ = 40

# Globals
g_sock = None
g_sockfd = None


if not os.path.isdir(SYSFS_NET_PATH):
    log.error("Path %s not found. This module requires sysfs.", SYSFS_NET_PATH)
    raise ImportError("Path %s not found. This module requires sysfs." % SYSFS_NET_PATH)

if not os.path.exists(PROCFS_NET_PATH):
    log.error("Path %s not found. This module requires procfs.", PROCFS_NET_PATH)
    raise ImportError("Path %s not found. This module requires procfs." % PROCFS_NET_PATH)


class Interface(object):
    """ Class representing a Linux network device.

    Attributes:
        name: name of the interface
    """

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<%s %s at 0x%x>" % (self.__class__.__name__, self.name, id(self))

    def up(self):
        """ Bring up the bridge interface. Equivalent to ifconfig [iface] up. """

        # Get existing device flags
        ifreq = struct.pack('16sh', self.name, 0)
        flags = struct.unpack('16sh', fcntl.ioctl(g_sockfd, SIOCGIFFLAGS, ifreq))[1]

        # Set new flags
        flags = flags | IFF_UP
        ifreq = struct.pack('16sh', self.name, flags)
        fcntl.ioctl(g_sockfd, SIOCSIFFLAGS, ifreq)

    def down(self):
        """ Bring up the bridge interface. Equivalent to ifconfig [iface] down. """

        # Get existing device flags
        ifreq = struct.pack('16sh', self.name, 0)
        flags = struct.unpack('16sh', fcntl.ioctl(g_sockfd, SIOCGIFFLAGS, ifreq))[1]

        # Set new flags
        flags = flags & ~IFF_UP
        ifreq = struct.pack('16sh', self.name, flags)
        fcntl.ioctl(g_sockfd, SIOCSIFFLAGS, ifreq)

    def is_up(self):
        """ Return True if the interface is up, False otherwise. """

        # Get existing device flags
        ifreq = struct.pack('16sh', self.name, 0)
        flags = struct.unpack('16sh', fcntl.ioctl(g_sockfd, SIOCGIFFLAGS, ifreq))[1]

        # Set new flags
        if flags & IFF_UP:
            return True
        else:
            return False

    def get_mac(self):
        """ Obtain the device's mac address.

        Return:
            the string format of mac, such as: '01:02:03:0a:0b:0c'
        """

        ifreq = struct.pack('16sH14s', self.name, AF_UNIX, '\x00' * 14)
        res = fcntl.ioctl(g_sockfd, SIOCGIFHWADDR, ifreq)
        address = struct.unpack('16sH14s', res)[2]
        mac = struct.unpack('6B8x', address)

        return ":".join(['%02X' % i for i in mac])

    def set_mac(self, new_mac):
        """ Set the device's mac address. Device must be down for this to succeed.

        Args:
            new_mac: the new mac address
        """

        mac_bytes = [int(i, 16) for i in new_mac.split(':')]
        ifreq = struct.pack('16sH6B8x', self.name, AF_UNIX, *mac_bytes)
        fcntl.ioctl(g_sockfd, SIOCSIFHWADDR, ifreq)

    def get_ip(self):
        """ Obtain the interface's ip address.

        Return:
            the string format of ip, such as: '192.168.1.2'
        """

        ifreq = struct.pack('16sH14s', self.name, AF_INET, '\x00' * 14)

        try:
            res = fcntl.ioctl(g_sockfd, SIOCGIFADDR, ifreq)
        except IOError:
            return None

        ip = struct.unpack('16sH2x4s8x', res)[2]

        return socket.inet_ntoa(ip)

    def set_ip(self, new_ip):
        """ Set the interface's ip address.

        Args:
            new_ip: the new ip address
        """

        ip_bytes = socket.inet_aton(new_ip)
        ifreq = struct.pack('16sH2s4s8s', self.name, AF_INET, '\x00' * 2, ip_bytes, '\x00' * 8)
        fcntl.ioctl(g_sockfd, SIOCSIFADDR, ifreq)

    def get_netmask(self):
        """ Obtain the interface's netmask.

        Return:
            netmask_len: the number of Binary '1' in the netmask (.e.g, 24)
            netmask_str: the string of netmask (.e.g, '255.255.255.0')
        """

        ifreq = struct.pack('16sH14s', self.name, AF_INET, '\x00' * 14)

        try:
            res = fcntl.ioctl(g_sockfd, SIOCGIFNETMASK, ifreq)
        except IOError:
            return 0, ''

        netmask = socket.ntohl(struct.unpack('16sH2xI8x', res)[2])

        netmask_str = socket.inet_ntoa(struct.pack('!I', netmask))
        netmask_len = 32 - int(round(math.log(ctypes.c_uint32(~netmask).value + 1, 2), 1))

        return netmask_len, netmask_str

    def set_netmask(self, netmask):
        """ Set the interface's netmask.

        Args:
            netmask: the number of Binary '1' in the net mask.
        """

        netmask = ctypes.c_uint32(~((2 ** (32 - netmask)) - 1)).value
        netmask_bytes = socket.htonl(netmask)
        ifreq = struct.pack('16sH2sI8s', self.name, AF_INET, '\x00' * 2, netmask_bytes, '\x00' * 8)
        fcntl.ioctl(g_sockfd, SIOCSIFNETMASK, ifreq)

    def get_index(self):
        """ Convert an interface name to an index value.

        Return:
            index value
        """

        ifreq = struct.pack('16si', self.name, 0)
        res = fcntl.ioctl(g_sockfd, SIOCGIFINDEX, ifreq)
        return struct.unpack("16si", res)[1]

    def get_link_info(self):
        """Get the link info of the interface.

        Return:
            speed: the forced speed, 10Mb, 100Mb, gigabit
            duplex: duplex, half or full
            auto: enable or disable auto negotiation
            up: up state(True means up, False means down)
        """

        # First get link params
        ecmd = array.array('B', struct.pack('I39s', ETHTOOL_GSET, '\x00' * 39))
        ifreq = struct.pack('16sP', self.name, ecmd.buffer_info()[0])
        try:
            fcntl.ioctl(g_sockfd, SIOCETHTOOL, ifreq)
            res = ecmd.tostring()
            speed, duplex, auto = struct.unpack('12xHB3xB24x', res)
        except IOError:
            speed, duplex, auto = 65535, 255, 255

        # Then get link up/down state
        ecmd = array.array('B', struct.pack('2I', ETHTOOL_GLINK, 0))
        ifreq = struct.pack('16sP', self.name, ecmd.buffer_info()[0])
        fcntl.ioctl(g_sockfd, SIOCETHTOOL, ifreq)
        res = ecmd.tostring()
        up = bool(struct.unpack('4xI', res)[0])

        if speed == 65535:
            speed = 0
        if duplex == 255:
            duplex = None
        else:
            duplex = bool(duplex)
        if auto == 255:
            auto = None
        else:
            auto = bool(auto)

        return speed, duplex, auto, up

    def set_link_mode(self, speed, duplex):
        """Set the link info of the interface.

        Args:
            speed: the forced speed, 10Mb, 100Mb, gigabit
            duplex: duplex, half or full
        """

        # First get the existing info
        ecmd = array.array('B', struct.pack('I39s', ETHTOOL_GSET, '\x00' * 39))
        ifreq = struct.pack('16sP', self.name, ecmd.buffer_info()[0])
        fcntl.ioctl(g_sockfd, SIOCETHTOOL, ifreq)
        # Then modify it to reflect our needs
        ecmd[0:4] = array.array('B', struct.pack('I', ETHTOOL_SSET))
        ecmd[12:14] = array.array('B', struct.pack('H', speed))
        ecmd[14] = int(duplex)
        ecmd[18] = 0  # Autonegotiation is off
        fcntl.ioctl(g_sockfd, SIOCETHTOOL, ifreq)

    def set_link_auto(self, ten=True, hundred=True, thousand=True):
        """Set the autonegotiation info of the interface.

        Args:
            ten:
            hundred:
            thousand:
        """

        # First get the existing info
        ecmd = array.array('B', struct.pack('I39s', ETHTOOL_GSET, '\x00' * 39))
        ifreq = struct.pack('16sP', self.name, ecmd.buffer_info()[0])
        fcntl.ioctl(g_sockfd, SIOCETHTOOL, ifreq)
        # Then modify it to reflect our needs
        ecmd[0:4] = array.array('B', struct.pack('I', ETHTOOL_SSET))

        advertise = 0
        if ten:
            advertise |= ADVERTISED_10baseT_Half | ADVERTISED_10baseT_Full
        if hundred:
            advertise |= ADVERTISED_100baseT_Half | ADVERTISED_100baseT_Full
        if thousand:
            advertise |= ADVERTISED_1000baseT_Half | ADVERTISED_1000baseT_Full

        newmode = struct.unpack('I', ecmd[4:8].tostring())[0] & advertise
        ecmd[8:12] = array.array('B', struct.pack('I', newmode))
        ecmd[18] = 1
        fcntl.ioctl(g_sockfd, SIOCETHTOOL, ifreq)

    def set_pause_param(self, autoneg, rx_pause, tx_pause):
        """
        Ethernet has flow control! The inter-frame pause can be adjusted, by
        auto-negotiation through an ethernet frame type with a simple two-field
        payload, and by setting it explicitly.

        http://en.wikipedia.org/wiki/Ethernet_flow_control
        """

        # create a struct ethtool_pauseparm
        # create a struct ifreq with its .ifr_data pointing at the above
        ecmd = array.array('B', struct.pack('IIII',
                                            ETHTOOL_SPAUSEPARAM,
                                            bool(autoneg),
                                            bool(rx_pause),
                                            bool(tx_pause)))
        logging.debug("ecmd %r %r", self.name, ecmd)
        buf_addr, _buf_len = ecmd.buffer_info()
        ifreq = struct.pack('16sP', self.name, buf_addr)
        fcntl.ioctl(g_sockfd, SIOCETHTOOL, ifreq)

    def get_stats(self):
        """Get the recive packets and transport packets statistic info

        Return:
            a dictionary of recive and transport packets statistic info.
        """

        spl_re = re.compile("\s+")

        with open(PROCFS_NET_PATH) as fp:
            # Skip headers
            fp.readline()
            fp.readline()
            while True:
                data = fp.readline()
                if not data:
                    return None

                name, stats_str = data.split(":")
                if name.strip() != self.name:
                    continue

                stats = [int(a) for a in spl_re.split(stats_str.strip())]
                break

        titles = ["rx_bytes", "rx_packets", "rx_errs", "rx_drop", "rx_fifo",
                  "rx_frame", "rx_compressed", "rx_multicast", "tx_bytes",
                  "tx_packets", "tx_errs", "tx_drop", "tx_fifo", "tx_colls",
                  "tx_carrier", "tx_compressed"]

        return dict(zip(titles, stats))

    index = property(get_index)
    mac = property(get_mac, set_mac)
    ip = property(get_ip, set_ip)
    netmask = property(get_netmask, set_netmask)


def iter_ifs(physical=True):
    """ Iterate over all the interfaces in the system. If physical is
        true, then return only real physical interfaces (not 'lo', etc).
    """

    net_files = os.listdir(SYSFS_NET_PATH)
    interfaces = set()
    virtual = set()
    for d in net_files:
        path = os.path.join(SYSFS_NET_PATH, d)
        if not os.path.isdir(path):
            continue
        if not os.path.exists(os.path.join(path, "device")):
            virtual.add(d)
        interfaces.add(d)

    # Some virtual interfaces don't show up in the above search, for example,
    # subinterfaces (e.g. eth0:1). To find those, we have to do an ioctl
    if not physical:
        # ifconfig gets a max of 30 interfaces. Good enough for us too.
        ifreqs = array.array("B", "\x00" * SIZE_OF_IFREQ * 30)
        buf_addr, _buf_len = ifreqs.buffer_info()
        ifconf = struct.pack("iP", SIZE_OF_IFREQ * 30, buf_addr)
        ifconf_res = fcntl.ioctl(g_sockfd, SIOCGIFCONF, ifconf)
        ifreqs_len, _ = struct.unpack("iP", ifconf_res)

        assert ifreqs_len % SIZE_OF_IFREQ == 0, (
            "Unexpected amount of data returned from ioctl. "
            "You're probably running on an unexpected architecture")

        res = ifreqs.tostring()
        for i in range(0, ifreqs_len, SIZE_OF_IFREQ):
            d = res[i: i + 16].strip('\0')
            interfaces.add(d)

    results = interfaces - virtual if physical else interfaces
    for d in results:
        yield Interface(d)


def find_if_by_name(name):
    for br in iter_ifs(True):
        if name == br.name:
            return br
    return None


def list_ifs(physical=True):
    """ Return a list of the names of the interfaces. If physical is
        true, then return only real physical interfaces (not 'lo', etc).
    """

    return [br.name for br in iter_ifs(physical)]


def init():
    """ Initialize the library """

    globals()["g_sock"] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    globals()["g_sockfd"] = globals()["g_sock"].fileno()


def shutdown():
    """ Shut down the library """

    if globals()["g_sock"]:
        globals()["g_sock"].close()
    globals()["g_sock"] = None
    globals()["g_sockfd"] = None


def ping_test(ip):
    """ ping network """
    ret = call('ping -c 2 -w 3 %s > /dev/null 2>&1' % ip, shell=True)
    if not ret:
        return True
    else:
        return False


def ping_server():
    config = ConfigParser.ConfigParser()
    config.read('/var/ovirt.conf')
    ip = config.get('oVirt', 'baseurl')
    ip = ip.strip()[len('https://'):]
    ip, _ = ip.split(':')
    if ping_test(ip):
        log.info('ping neiwang success!')
        return True
    else:
        return False



# Do this when loading the module
init()
