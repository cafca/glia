#!/usr/bin/env python

# This script adds a host entry for app.soma => 127.0.0.1
# so the app can be accessed at app.soma"""

# TODO: Where is hosts on Windows?
HOSTSFILE = '/etc/hosts'
SOMA_ENTRY = "127.0.0.1 app.soma"
entry_found = False


def test_host_entry():
    """Return True if the right entry is found in the hosts file"""
    with open(HOSTSFILE) as f:
        for line in f.readlines():
            if line == SOMA_ENTRY:
                return True


if test_host_entry() is False:
    print "[soma] adding entry for app.soma to etc/hosts.."
    with open(HOSTSFILE, 'a') as f:
        f.write("\n\n# Access Soma at app.soma\n" + SOMA_ENTRY)
else:
    print "[soma] hosts entry found"
