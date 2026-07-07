class XConnector:
    tier = "api"
    def __init__(self, bearer_token, http_get=None):
        self.bearer_token = bearer_token
        self._http_get = http_get
