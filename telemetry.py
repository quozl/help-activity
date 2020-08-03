#
# Copyright (C) 2019 One Laptop per Child, Inc
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301
# USA
#

import os
import socket
from gi.repository import GLib
from gi.repository import Gio


# telemetry logging server name
HOST = 'crank.laptop.org'

# port server listens on
PORT = 7404

# milliseconds to defer transmission by
WHEN = 111


_OFW_TREE = '/ofw'
_PROC_TREE = '/proc/device-tree'
_DMI_DIRECTORY = '/sys/class/dmi/id'
_not_available = 'unknown'
_serial_no = None


def _read_file(path):
    if os.access(path, os.R_OK) == 0:
        return None

    fd = open(path, 'r')
    value = fd.read()
    fd.close()
    if value:
        value = value.strip('\n')
        return value
    return None


def _read_device_tree(path):
    value = _read_file(os.path.join(_PROC_TREE, path))
    if value:
        return value.strip('\x00')
    value = _read_file(os.path.join(_OFW_TREE, path))
    if value:
        return value.strip('\x00')
    return value


def _get_serial_number():
    serial_no = _read_device_tree('serial-number')
    if serial_no is not None:
        return serial_no

    cmd = 'pkexec sugar-serial-number-helper'
    result, output, error, status = GLib.spawn_command_line_sync(cmd)
    if status != 0:
        return _not_available

    serial_no = output.decode().rstrip('\n')
    if len(serial_no) == 0:
        return _not_available

    return serial_no


def get_serial_number():
    global _serial_no

    if _serial_no is None:
        _serial_no = _get_serial_number()

    return _serial_no


class Telemetry():
    def __init__(self, text):
        global HOST

        if 'OLPC_TELEMETRY_HOST' in os.environ:
            HOST = os.environ['OLPC_TELEMETRY_HOST']

        packet = 'olpc telemetry ' + get_serial_number() + ' ' + \
                 os.environ['SUGAR_VERSION'] + ' ' + \
                 os.environ['SUGAR_BUNDLE_ID'] + ' ' + \
                 os.environ['SUGAR_BUNDLE_VERSION'] + ' ' + text
        GLib.timeout_add(WHEN, self._idle_cb, packet)

    def _idle_cb(self, packet):
        Gio.Resolver.get_default().lookup_by_name_async(
            HOST, None, self._resolver_cb, packet)
        return False

    def _resolver_cb(self, source, result, packet):
        ip = source.lookup_by_name_finish(result)[0].to_string()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(packet, (ip, PORT))
