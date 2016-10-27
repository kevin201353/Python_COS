#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2015 ShenCloud Inc.
#

"""
Read network infor to config and save it to file
encrypt and decrypt passwd
"""

import logging
import re
from subprocess import Popen

log = logging.getLogger(__name__)

RESTART_NEWTORK_SERVICE = ["/etc/init.d/networking", "restart"]
IFCONFIG = 'ifconfig -a |grep Ethernet| awk -F\" \" \'{print $1}\''
INTERFACE_FILE = '/etc/network/interfaces'
DNS_FILE = '/etc/resolv.conf'

WLAN_CONF_TEMP = '''    wireless_mode maneged
    wireless_essid managed
    wpa-driver wext
    wpa-conf /etc/wpa_supplicant.conf
'''
DHCP_TEMPLATE = '''auto %s
iface %s inet dhcp
'''
WLAN_DHCP_TEMPLATE = DHCP_TEMPLATE + WLAN_CONF_TEMP
STATIC_IP_TEMPLATE = '''auto %s
iface %s inet static
    address %s
    netmask %s
    gateway %s
'''
WLAN_STATIC_IP_TEMPLATE = STATIC_IP_TEMPLATE + WLAN_CONF_TEMP

DNS_TEMPLATE = '''nameserver %s
'''

def str2bool(value):
    return str(value).lower() in ("true", "t", "1", "yes", "y")


def encrypt(key, s):
    """ encrypt the password

    Args:
        key: password key
        s: real password
    """

    b = bytearray(str(s).encode("utf8"))
    n = len(b)
    c = bytearray(n * 2)
    j = 0
    for i in range(0, n):
        b1 = b[i]
        b2 = b1 ^ key
        c1 = b2 % 16
        c2 = b2 // 16
        c1 = c1 + 65
        c2 = c2 + 65
        c[j] = c1
        c[j + 1] = c2
        j = j + 2
    return c.decode("utf8")


def decrypt(key, s):
    """ decrypt the password

    Args:
        key: password key
        s: real password
    """

    c = bytearray(str(s).encode("utf8"))
    n = len(c)
    if n % 2 != 0:
        return ""
    n = n // 2
    b = bytearray(n)
    j = 0
    for i in range(0, n):
        c1 = c[j]
        c2 = c[j + 1]
        j = j + 2
        c1 = c1 - 65
        c2 = c2 - 65
        b2 = c2 * 16 + c1
        b1 = b2 ^ key
        b[i] = b1

    return b.decode("utf8")


def config_ethernet(ip_description, dns_setting, wlan_on=False):
    """save ip and dns to file.

    Args:
         ip_description: value: ip information read file /etc/network/interfaces
                        key: interface name
         dns_setting: dns  read file /etc/resolv.conf
    """

    ip_settings = ''
    for key in ip_description.keys():
        if ip_description[key].strip():
            ip_settings = ip_settings + '\n' + ip_description[key]

    write_file(ip_settings, dns_setting)

    log.debug('Restarting network service...\n\t%s\n\t%s',
              ip_settings, dns_setting)

    with open(INTERFACE_FILE, 'r') as net_file:
        net_info = net_file.readlines()
        static_flag = False
        net_ip = net_mask = gate_way = ''
        for line in net_info:
            if 'dhcp' in line:
                if_name = line.split()[1].strip()
                if wlan_on and not if_name.startswith('wlan'):
                    continue
                Popen("sudo kill `ps aux | grep dhclient | grep %s | grep -v grep | awk '{print $2}'` > /dev/null 2>&1" % if_name,
                      shell=True)
               # Popen("sudo route del default", shell=True)
               # Popen("sudo /etc/init.d/networking stop", shell=True)
               # Popen("sudo ifconfig %s 0.0.0.0" % if_name, shell=True)
               # Popen("sudo dhclient %s > /dev/null 2>&1" % if_name, shell=True)
                Popen("sudo /etc/init.d/networking restart", shell=True)
                continue
            elif 'static' in line:
                if_name = line.split()[1].strip()
                if wlan_on and not if_name.startswith('wlan'):
                    continue
                static_flag = True
                continue

            if 'address' in line:
                net_ip = line.strip()[7:].strip().strip('\n')
            elif 'netmask' in line:
                net_mask = line.strip()[7:].strip().strip('\n')
            elif 'gateway' in line:
                gate_way = line.strip()[7:].strip().strip('\n')

            if static_flag and net_ip and net_mask and gate_way:
                static_flag = False
                Popen("sudo kill `ps aux | grep dhclient | grep %s | grep -v grep | awk '{print $2}'` > /dev/null 2>&1" % if_name,
                      shell=True)
                Popen("sudo route del default", shell=True)
                cmd = 'sudo ifconfig %s %s netmask %s' % (if_name, net_ip, net_mask)
                Popen("sudo ifconfig %s up" % if_name, shell=True)
                #Popen("sudo /etc/init.d/networking restart", shell=True)
                Popen(cmd, shell=True)
                Popen("sudo route add default gw %s %s" % (gate_way, if_name), shell=True)
                net_ip = net_mask = gate_way = ''

def process_netconfig(eth, is_dhcp=True, ipaddr=None, netmask=None, gateway=None):
    """ use dhcp or static ip access ipaddr, netmask, gateaway
    when static ip, if ipaddr, netmask, gateaway format error
    print error message, return False

    Args:
        eth: interface name, for example eth0
        is_dhcp: to detemine whether dhcp, False means static ip
    """

    eth = eth.strip('\n')

    if is_dhcp:
        if eth.startswith('wlan'):
            ip_setting = WLAN_DHCP_TEMPLATE % (eth, eth)
        else:
            ip_setting = DHCP_TEMPLATE % (eth, eth)
    else:
        errmsg = ''
        ret = True
        if not ip_format_check(ipaddr):
            errmsg += '无效的IP地址：' + ipaddr + '\n'
            ret = False

        if not ip_format_check(netmask):
            errmsg += '无效的子网掩码：' + netmask + '\n'
            ret = False

        if not ip_format_check(gateway):
            errmsg += '无效的网关：' + gateway + '\n'
            ret = False
        if ret:
            if eth.startswith('wlan'):
                ip_setting = WLAN_STATIC_IP_TEMPLATE % (eth, eth, ipaddr, netmask, gateway)
            else:
                ip_setting = STATIC_IP_TEMPLATE % (eth, eth, ipaddr, netmask, gateway)
        else:
            return False, errmsg

    return True, ip_setting

def get_static_ipinfo_by_name(if_name):
    """when the interface set to static, return the ip、netmask
    and gate way.

    Args:
        if_name: interface name, for example eth0
    """

    net_ip = net_mask = gate_way = ''
    with open(INTERFACE_FILE, 'r') as net_file:
        net_info = net_file.readlines()
        static_flag = False
        for line in net_info:
            if 'dhcp' in line:
                continue
            elif 'static' in net_info:
                if if_name == line.split()[1].strip():
                    static_flag = True
                continue
            if 'address' in line:
                if static_flag:
                    net_ip = line.strip()[7:].strip().strip('\n')
                continue
            if 'netmask' in line:
                if static_flag:
                    net_mask = line.strip()[7:].strip().strip('\n')
                continue
            if 'gateway' in line:
                if static_flag:
                    gate_way = line.strip()[7:].strip().strip('\n')
                continue
            if static_flag and net_ip and net_mask and gate_way:
                static_flag = False
                break
    return net_ip, net_mask, gate_way

def process_dnsconfig(dns):
    """ get dns information and return it
    if input dns format error print error message and return False
    """

    dummy_dns_server = ''  # dummy_ prefix is used to clear pep8 warning
    if not ip_format_check(dns):
        errmsg = '无效的DNS:' + dns
        return False, errmsg
    dummy_dns_server = 'nameserver ' + dns

    return True, dummy_dns_server


def read_dnsfile():
    """ read dns information from file /etc/resolv.conf """

    with open(DNS_FILE, 'r') as dns_file:
        dns_setting = dns_file.readlines()

    dns = ''
    for s in dns_setting:
        if 'nameserver' in s and '#' not in s:
            dns = s
            break

    return dns


def read_file(dest_nics):
    """read interfaces information from /etc/network/interfaces
    to dest_nics value,and return dest_dict

    Args:
       dest_nics: key: interface name, value: interface information
    """

    temp_info = ''
    dest_dict = {}
    curnic = ''
    for e in dest_nics:
        dest_dict[e] = ''

    with open(INTERFACE_FILE, 'r') as interface_file:
        lines = interface_file.readlines()
        for s in lines:
            if s.strip().startswith('auto '):
                try:
                    if_name = s.split(' ')[1].strip()
                except:
                    continue
                if if_name not in dest_nics:
                    curnic = ''
                    continue
                if not curnic:
                    curnic = if_name
                    dest_dict[curnic] = ''
                else:
                    dest_dict[curnic] = temp_info
                    curnic = if_name
                temp_info = s
            elif s.strip('\n') and not s.startswith('#'):
                temp_info += s

        if temp_info:
            dest_dict[curnic] = temp_info

    return dest_dict


def write_file(ip_setting, dns_setting):
    """write ip information and dns information to file

    Args:
        ip_setting: ip information
        dns_setting: dns information
    """

    with open(INTERFACE_FILE, 'w') as interface_file:
        interface_file.write(ip_setting)

    write_dns(dns_setting)

def write_dns(dns_setting):
    if dns_setting != '':
        with open(DNS_FILE, 'w') as dns_file:
            dns_setting = DNS_TEMPLATE % dns_setting
            dns_file.write(dns_setting)

def ip_format_check(ip_str):
    """ check ip addr format """

    if not ip_str:
        return False

    pattern = r"\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    if re.match(pattern, ip_str):
        return True
    else:
        return False


if __name__ == '__main__':
    read_dnsfile()
