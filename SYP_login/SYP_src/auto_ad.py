#!/usr/bin/python

from time import sleep
from subprocess import Popen, PIPE, call, CalledProcessError, STDOUT
try:
    from subprocess import check_output
except ImportError:
    def func(*popenargs, **kwargs):
        if 'stdout' in kwargs:
            raise ValueError('stdout argument not allowed, it will be overridden.')
        process = Popen(stdout=PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            raise CalledProcessError(retcode, cmd)
        return output
    check_output = func

DNS_FILE = '/etc/resolv.conf'


def get_dns1():
    for line in open(DNS_FILE):
        if line.startswith('nameserver'):
            dns = line.split()[1].split('#')[0]
            return dns
    return None


def detect_ad(ad_ip, port):
    ad_port = port
    cmd = ['telnet', ad_ip, str(ad_port)]
    p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    #output = check_output(['ls', '-l'], shell=True)
    output, err = p.communicate("echo -e '\n'")
    info = 'Connected to %s.' % ad_ip
    if info in output:
        # print 'telnet %s %s Sucessful!' % (ad_ip, ad_port)
        return True
    # print 'telnet %s %s Failed!' % (ad_ip, ad_port)
    return False


def ping_test(ip):
    ret = call('ping -c 2 -w 10 %s > /dev/null 2>&1' % ip, shell=True)
    if not ret:
        # print 'ping %s success.' % ip
        return True
    else:
        # print 'ping %s failed!' % ip
        return False

ad_ports = [135, 389, 636, 3268, 3269, 53, 88, 445]
if __name__ == '__main__':
    while True:
        ad_ip = get_dns1()
        if ping_test(ad_ip):
            for port in ad_ports:
                while True:
                    if detect_ad(ad_ip, port):
                        #print port, 'ok'
                        break
                    sleep(1)
            else:
                call('service ovirt-engine restart', shell=True)
                #print 'service ovirt-engine restart'
                break
        sleep(1)
