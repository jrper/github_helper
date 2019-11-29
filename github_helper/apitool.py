"""Module containing a class to wrap HTTP calls to the GitHub REST
API.
"""

import collections
import json
from urllib import request, error

__all__ = ['GithubAPI']

def _process_response(resp):
    """Process an HTTP response into JSON."""
    if resp.length:
        return json.load(resp)
    return None


class ResponseCache():

    def __init__(self, maxsize=100):
        self.maxsize = maxsize
        self._data = collections.OrderedDict()
    
    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, val):
        if key in self._data:
            del self._data[key]
        self._data[key] = val
        while len(self._data) > self.maxsize:
            self._data.popitem()

    def __contains__(self, key):
        return key in self._data
            

class GithubAPI():
    """Class to wrap calls to the GitHub api."""

    base_url = "https://api.github.com"

    def __init__(self, token=None, error_handler=None, cachesize=100):
        self.set_token(token)
        self.error_handler = error_handler
        self._cache = ResponseCache(cachesize)

    def set_token(self, token):
        """Set the personal access token for subsequent calls."""
        self.token = token

    def __call__(self, endpoint, http_method=None, **data):

        if data:
            data = str(json.dumps(data)).encode('utf-8')
        else:
            data = None

        req = request.Request(self.base_url+endpoint,
                              method=http_method,
                              data=data)
        
        req.add_header('content-type', 'application/json')
        if self.token:
            req.add_header('Authorization', f'token {self.token}')

        etag = None
        if endpoint in self._cache:
            etag = self._cache[endpoint][0].get('ETag', None)
            
        if etag:
            req.add_header('If-None-Match', etag)
            
        try:
            resp = request.urlopen(req)
            self._cache[endpoint] = resp.headers, _process_response(resp)
        except error.HTTPError as err:
            if err.code == 304:
                pass
            elif self.error_handler:
                self.error_handler(err)
                return err
            else:
                raise err
        return self._cache[endpoint][1]
