class ScrapeCreatorsConnector:
    tier = "scrape"
    def __init__(self, api_key, platform, http_get=None):
        self.api_key = api_key
        self.platform = platform
        self._http_get = http_get
