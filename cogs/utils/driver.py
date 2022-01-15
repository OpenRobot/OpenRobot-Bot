import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class Driver:
    def __init__(self, *, use_proxy: bool = False, proxy: str = None):
        self.proxy: bool = proxy
        self.use_proxy = use_proxy

        self.driver = None

    def __exit__(self, exc_type, exc_value, traceback):
        if self.driver:
            self.driver.close()

    def __enter__(self):
        if self.use_proxy:
            if not self.proxy:
                proxy = self._get_proxy()
                addr = proxy["ip"] + ":" + str(proxy["port"])
            else:
                addr = self.proxy
        else:
            proxy = None
            addr = None

        chrome_options = Options()

        if addr:
            chrome_options.add_argument("--proxy-server=%s" % addr)

        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")

        self.driver = webdriver.Chrome(
            "/usr/lib/chromium-browser/chromedriver", options=chrome_options
        )

        return self.driver

    @staticmethod
    def _get_proxy():
        url = r"https://api.getproxylist.com/proxy?minUptime=75&allowsHttps=1&allowsCookies=1&protocol[]=http&allowsCustomHeaders=1&allowsUserAgentHeader=1&/proxy?anonymity[]=high%20anonymity&anonymity[]=anonymous&allowsPost=1"

        r = requests.get(url)

        return r.json()
