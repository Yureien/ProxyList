from proxybroker.api import Broker
import requests
import asyncio
import logging
import multiprocessing
from queue import Empty
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class ListMaker:
    def __init__(
            self, limit=40, max_resp_time=2.0, countries=None, max_list_length=500,
            anonymity=None, types=['HTTP', 'HTTPS', 'SOCKS4', 'SOCKS5'],
            test_sites=['https://google.com', 'https://en.wikipedia.org', 'https://nhentai.net']):
        try:
            multiprocessing.set_start_method('spawn')
        except RuntimeError:
            if multiprocessing.get_start_method() is not 'spawn':
                raise RuntimeError(
                    "Multiprocessing method of starting child processes has to be 'spawn'")
        self.results_queue = multiprocessing.Queue()
        self._poison_pill = multiprocessing.Event()
        self._proxy_finder = ProxyFinderProcess(
            self.results_queue, self._poison_pill, limit=limit,
            max_resp_time=max_resp_time, countries=countries,
            anonymity=anonymity, types=types, test_sites=test_sites)
        self.proxy_list = []
        self.max_list_length = max_list_length

    def start(self):
        self._proxy_finder.start()
        logging.info("A new proxy finder is born.")

    def get_n_proxies(self, n):
        self.start()
        while True:
            try:
                proxy = self.results_queue.get_nowait()
            except Empty:
                break
            else:
                self.proxy_list.append(proxy)
            n -= 1
            if n <= 0:
                break
        self.stop()
        return self.get_simple_list()

    def stop(self):
        self._poison_pill.set()
        self._proxy_finder.join()
        logging.info("The proxy finder is poisoned to death.")

    def update_proxies(self):
        while True:
            try:
                proxy, fetched_at = self.results_queue.get_nowait()
            except Empty:
                break
            else:
                self.proxy_list.append((proxy, fetched_at))
        if len(self.proxy_list) > self.max_list_length:
            self.proxy_list = self.proxy_list[self.max_list_length//4:]

    def get_list(self):
        return self.proxy_list

    def get_simple_list(self):
        simple_list = []
        for proxy, fetched_at in self.proxy_list:
            proxy_type = list(proxy.types.keys())[0]
            anonymity = None
            if 'HTTP' == proxy_type:
                anonymity = proxy.types['HTTP']
            simple_list.append({
                'type': proxy_type,
                'host': proxy.host,
                'port': proxy.port,
                'avg_resp_time': proxy.avg_resp_time,
                'country_code': proxy.geo[0],
                'country_name': proxy.geo[1],
                'is_working': proxy.is_working,
                'anonymity': anonymity,
                'fetched_at': fetched_at
            })
        return simple_list


class ProxyFinderProcess(multiprocessing.Process):
    def __init__(self, proxy_queue, poison_pill, limit=40,
                 max_resp_time=1.0, countries=None, anonymity=None,
                 types=['HTTP', 'HTTPS', 'SOCKS4', 'SOCKS5'],
                 test_sites=['https://google.com', 'https://en.wikipedia.org']):
        multiprocessing.Process.__init__(self)
        self.results_queue = proxy_queue
        self.poison_pill = poison_pill
        self.max_resp_time = max_resp_time
        if types is not None and anonymity is not None and "HTTP" in types:
            types.remove("HTTP")
            types.append(("HTTP", tuple(anonymity)))
        self.types = types
        self.countries = countries
        self.limit = limit
        self.proxy_list = []
        self.test_sites = test_sites

    def _basic_test_proxy(self, proxy):
        if proxy.avg_resp_time > self.max_resp_time:
            return False
        proxy_type = list(proxy.types.keys())[0].lower()
        url = "{0}://{1}:{2}".format(proxy_type, proxy.host, str(proxy.port))
        logging.debug("Proxy URL: %s" % (url,))
        proxy_dict = {'http': url, 'https': url, 'ftp': url}
        for test_site in self.test_sites:
            try:
                requests.get(test_site, proxies=proxy_dict, timeout=1)
                logging.info("Working Proxy: %s" % (proxy,))
            except (requests.exceptions.ProxyError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout):
                return False
        return True

    async def async_to_results(self):
        while not self.poison_pill.is_set():
            proxy = await self.async_queue.get()
            if proxy is None:
                break
            else:
                if self._basic_test_proxy(proxy) is False:
                    continue
                self.results_queue.put((proxy, datetime.now()))
        self.broker.stop()

    def run(self):
        self.async_queue = asyncio.Queue()
        self.broker = Broker(queue=self.async_queue, timeout=2, max_tries=1, verify_ssl=True)
        self.tasks = asyncio.gather(
            self.broker.find(types=self.types, countries=self.countries,
                             strict=True, limit=self.limit),
            self.async_to_results())
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.tasks)


# For testing
# list_maker = ListMaker(limit=8)
# list_maker.make_list()
# print(list_maker.get_list())
# print(list_maker.get_simple_list())
