"""
A http proxy based on the SocketServer Module
Author: Jonas Wagner
Version: 0.1
Last Change: 2008-06-23

HTTPRipper a generic ripper for the web
Copyright (C) 2008 Jonas Wagner

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import atexit
from datetime import datetime
from os import path
import SocketServer
import shutil
import sys
import socket
import tempfile
import urllib2
from urlparse import urlparse


import logging
logger = logging

socket.setdefaulttimeout(30)


class HTTPProxyHandler(SocketServer.StreamRequestHandler):
    def parse_request(self):
        """parse a request line"""
        request = ""
        while not request:
            request = self.rfile.readline().strip()
        logger.debug("request %r", request)
        method, rawurl, version = request.split(" ")
        return method, rawurl, version

    def parse_header(self, f):
        """read the httpheaders from the file like f into a dictionary"""
        logger.debug("processing headers")
        headers = {}
        for line in f:
            if not line.strip():
                break
            key, value = line.split(": ", 1)
            headers[key] = value.strip()
        return headers

    def write_headers(self, f, headers):
        """
        Forward the dictionary containing httpheaders *headers*
        to the file f. Writes a newline at the end.
        """
        logger.debug("forwarding headers %r", headers)
        for item in headers.items():
            if not item[0].startswith("Proxy-"):
                f.write("%s: %s\r\n" % item)
        f.write("\r\n")

    def forward(self, f1, f2, maxlen=0):
        """forward maxlen bytes from f1 to f2"""
        logger.debug("forwarding %r bytes", maxlen)
        left = maxlen or 1000000000
        while left:
            data = f1.read(min(left, 1024))
            if not data:
                break
            f2.write(data)
            left -= len(data)

    forward_request_body = forward
    forward_response_body = forward

    def request_url(self, method, url):
        """create a new socket and write the requestline"""
        url = urlparse(url)
        request = "%s %s%s HTTP/1.0\r\n" % (method, url.path or "/",
                url.query and "?" + url.query or "")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((url.hostname, int(url.port or 80)))
        s.sendall(request)
        return s, s.makefile("rwb", 0)

    def handle(self):
        """Handle client requests"""
        while True:
            method, url, version = self.parse_request()
            self.url = url
            requestheaders = self.parse_header(self.rfile)
#            requestheaders["Connection"] = "close"
            sock, request = self.request_url(method, url)
            self.write_headers(request, requestheaders)
            if method in ("POST", "PUT") and "Content-Length" in requestheaders:
                self.forward_request_body(self.rfile, request,
                        int(requestheaders["Content-Length"]))
            # forward status line
            self.wfile.write(request.readline())
            responseheaders = self.parse_header(request)
            self.write_headers(self.wfile, responseheaders)
            try:
                clen = int(responseheaders.get("Content-Length"))
            except (KeyError, TypeError):
                clen = None
            self.forward_response_body(request, self.wfile, clen)
            request.close()
            sock.close()
            if requestheaders.get("Proxy-Connection") != "keep-alive":
                break
            break

class HTTPProxyServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr):
        SocketServer.TCPServer.__init__(self, addr, HTTPProxyHandler)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    server = HTTPProxyServer(("localhost", 8080))
    server.record = True
    server.serve_forever()

