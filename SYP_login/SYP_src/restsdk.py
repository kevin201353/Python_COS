
import logging
from time import time
from xml.etree import cElementTree as Elementree

import requests

MB = 1024*1024
GB = MB*1024

log = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.WARNING)
requests.packages.urllib3.disable_warnings()

class API(object):
    def __init__(self):
        self.__baseurl = None
        self.__session = None
        self.__parser = XmlParser()


    def login(self, url, username, password):
        self.__baseurl = url
        headers = {'Content-Type': 'application/xml'}
        headers['Prefer'] = 'persistent-auth'
        headers['Connection'] = 'close'
        if not username.endswith("@internal"):
            headers['filter'] = 'true'
        self.__session = requests.Session()
        self.__session.headers.update(headers)
        self.__session.auth = requests.auth.HTTPBasicAuth(username, password)
        self.__session.verify = False

        try:
            start = time()
            req = None
            req = self.__session.get(self.__baseurl, timeout=10, stream=True)
            if req.status_code == 200:
                log.debug("Login %s request spend %s seconds" % (username, time()-start))
                self.__session.auth = None
                return True, ''
            else:
                log.debug("%s\nStatusCode %s\nContent:%s\n%s" % ('-'*30, req.status_code, req.content, '-'*30))
                err = 'Invalid'
        except requests.Timeout as e:
            log.debug("Login %s Timeout %s" % (username, e))
            err = 'Timeout'
        except requests.RequestException as e:
            log.debug("Login %s RequestException %s" % (username, e))
            err = 'Request'
        except requests.ConnectionError as e:
            log.debug("Login %s ConnectionError %s" % (username, e))
            err = 'Connection'
        except requests.exceptions as e:
            log.debug("Login %s Exception %s" % (username, e))
            err = 'Exception'
        try:
            self.__session.close()
        except Exception as e:
            log.debug("Login %s session close error: %s " % (username, e))
            pass
        self.__session = None

        return False, err

    def logout(self):
        if self.__session:
            log.debug("Session logout")
            try:
                self.__session.close()
                self.__session = None
            except Exception as e:
                self.__session = None
                log.debug("Logout error: %s" % e)

    def getDiskInfo(self, vmid):
        requestUrl = "%s/vms/%s/disks" % (self.__baseurl, vmid)
        diskInfo = self.request(requestUrl, method="get")
        return diskInfo

    def getVmInfo(self, vmid=None):
        if vmid:
            requestUrl = "%s/vms/%s" % (self.__baseurl, vmid)
        else:
            requestUrl = "%s/vms" % self.__baseurl
        vmInfo = self.request(requestUrl, method="get")
        return vmInfo


    def getVmTicket(self, vmid, expire=7*24*60*60):
        requestUrl = "%s/vms/%s/ticket" % (self.__baseurl, vmid)
        data = '<action><ticket><expiry>%s</expiry></ticket></action>' % expire
        ticket = self.request(requestUrl, method="post", data=data)
        return ticket

    def handleVm(self, vmid, operation):
        if operation in ['start', 'stop', 'shutdown']:
            requestUrl = "%s/vms/%s/%s" % (self.__baseurl, vmid, operation)
            data = '<action></action>'
            self.request(requestUrl, method="post", data=data, timeout=3)
            return True
        else:
            log.debug("Disallowed operation")
            return False

    def request(self, url, method, data=None, timeout=20):
        parser = None

        if not self.__session:
            log.debug("Request No login")
            return None

        try:
            start = time()
            if method == "get":
                req = self.__session.get(url, verify=False, timeout=timeout)
            elif method == "post":
                req = self.__session.post(url, verify=False, data=data, timeout=timeout)
            interval = time() - start
        except requests.Timeout:
            interval = time() - start
            log.debug("Request %s Timeout %s second" % (url, interval))
            return None
        except requests.RequestException as e:
            interval = time() - start
            log.debug("Request %s RequestException %s second\nError: %s" % (url, interval, e))
            return None
        except requests.ConnectionError as e:
            interval = time() - start
            log.debug("Request %s ConnectionError %s second\nError: %s" % (url, interval, e))
            return None
        except requests.exceptions as e:
            interval = time() - start
            log.debug("Request %s Exception %s second\nError: %s" % (url, interval, e))
            return None

        if req.status_code == 200:
            log.debug("Request: %s, succeed %s second" % (url, interval))
            parser = self.__parser.parse(url, req.content)
        else:
            log.debug("%s\nInterval %s second\nStatusCode %s\nContent:%s\n%s" % ('-'*30, interval, req.status_code, req.content, '-'*30))

        return parser

class XmlParser(object):

    def parse(self, url, xml):
        fun = self.checkurl(url)
        return fun(xml)

    def checkurl(self, url):
        if url.endswith("disks"):
            return self.diskInfo
        elif url.endswith("ticket"):
            return self.ticketInfo
        elif url.endswith("start") or \
             url.endswith("stop") or \
             url.endswith("shutdown"):
            return self.handleInfo
        elif 'vms' in url:
            return self.vmsInfo

    def findtext(self, node, label):
        text = ''
        try:
            text = node.find(label).text
        except Exception:
            pass
        return text

    def vmInfo(self, node):
        vm = {}
        vm["id"] = node.attrib['id']
        for att in node:
            if att.tag == 'name':
                vm["name"] = att.text
            elif att.tag == 'status':
                vm["state"] = self.findtext(att, 'state')
            elif att.tag == 'memory':
                vm["mem"] = int(att.text) / float(MB)
            elif att.tag == 'display':
                vm['disp'] = self.findtext(att, 'type')
                if vm['disp'] == 'spice':
                    vm['disp'] = 'SYP'
                vm['url'] = self.findtext(att, 'address')
                vm['port'] = self.findtext(att, 'port')
                secure_port = self.findtext(att, 'secure_port')
                if secure_port:
                    vm['secure_port'] = secure_port
                else:
                    vm['secure_port'] = None
            elif att.tag == 'cpu':
                cpu = att.find('topology').attrib
                vm['cpu'] = int(cpu['cores']) * int(cpu['sockets'])
            elif att.tag == 'usb':
                vm['usb'] = self.findtext(att, 'enabled')
            vm['disk'] = 0
        return vm

    def vmsInfo(self, xml):
        vms = []
        rootTree = Elementree.fromstring(xml)
        if rootTree.tag == 'vms':
            for node in rootTree:
                vm = self.vmInfo(node)
                vms.append(vm)
        elif rootTree.tag == 'vm':
            vms = self.vmInfo(rootTree)
        return vms

    def diskInfo(self, xml):
        disksize = 0
        rootTree = Elementree.fromstring(xml)
        for node in rootTree:
            for att in node:
                if att.tag == 'size':
                    disksize += int(att.text)

        return disksize / float(GB)

    def ticketInfo(self, xml):
        try:
            return Elementree.fromstring(xml).find("ticket").find("value").text
        except Exception:
            return None

    def handleInfo(self, xml):
        return xml



BASEURL = "https://192.168.130.250:443/ovirt-engine/api"
if __name__ == "__main__":
    from time import sleep
    from multiprocessing import Pool

    format_ = '%(asctime)s  %(filename)s[line:%(lineno)d] \n\t[%(levelname)s] %(message)s'
    logging.basicConfig(level=logging.DEBUG,
                        format=format_,
                        filename='restsdk.log',
                        filemode='w')
    def testunit(account):
        while True:
            api = API()
            ret, info = api.login(url=BASEURL, username=account, password="123456")
            if ret:
                api.getVmInfo()
                sleep(1)
            else:
                return
            api.logout()

    accounts = ["stu%s@eclass.com" % i for i in range(1, 31)]

    pool = Pool(len(accounts))
    for account in accounts:
        pool.apply_async(testunit, (account,))
    pool.close()
    pool.join()

