from flask import Request

class ProxiedRequest(Request):
    """
    `Request` subclass that overrides `remote_addr` with Frontend Server's
    HTTP_X_FORWARDED_FOR when available.
    """

    @property
    def remote_addr(self):
        """The remote address of the client."""
        # Get a parsed version of X-Forwarded-For header (contains
        #    REMOTE_ADDR if no forwarded-for header). See
        #    http://en.wikipedia.org/wiki/X-Forwarded-For
        fwd = self.access_route
        remote = self.environ.get('REMOTE_ADDR', None)
        if fwd and self._is_private_ip(remote):
            # access route is a list where the client is first
            # followed by any intermediary proxies. However, we
            # can only trust the last entry as valid -- it's from
            # the server one hop behind the one connecting.
            return fwd[-1]
        else:
            return remote

    def _is_private_ip(self,ip):
        blank_ip = (ip is None or ip == '')
        private_ip = (ip.startswith('10.') or ip.startswith('172.16.') or ip.startswith('192.168.'))
        local_ip = (ip == '127.0.0.1' or ip == '0.0.0.0')
        return blank_ip or private_ip or local_ip

## use this class so we get real IPs
# from real_ip_address import ProxiedRequest
# app = [...]
# app.request_class = ProxiedRequest
