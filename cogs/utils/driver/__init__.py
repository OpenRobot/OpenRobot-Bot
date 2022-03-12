from .proxy import get_proxy
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class Driver:
    def __init__(self, *, ad_block: bool = False, use_proxy: bool = False, proxy: str = None):
        self.ad_block = ad_block
        self.use_proxy = use_proxy
        self.proxy = proxy

        self.driver = None

    def __exit__(self, exc_type, exc_value, traceback):
        if self.driver:
            self.driver.close()

    def __enter__(self):
        if self.use_proxy or self.proxy:
            if not self.proxy:
                addr = self.get_proxy()
            else:
                addr = self.proxy
        else:
            proxy, addr = None, None

        chrome_options = Options()

        if addr:
            chrome_options.add_argument(f"--proxy-server={addr}")

        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")

        if self.ad_block:
            chrome_options.add_extension("/home/ubuntu/adblock_ext.crx")

        self.driver = webdriver.Chrome(
            "/home/ubuntu/chromedriver", options=chrome_options
        )

        return self.driver

    @staticmethod
    def get_proxy():
        proxy = get_proxy()

        if not proxy:
            return None

        return proxy["host"] + ":" + str(proxy["port"])
