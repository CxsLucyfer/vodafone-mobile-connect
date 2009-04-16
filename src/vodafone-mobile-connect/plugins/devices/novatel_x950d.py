# -*- coding: utf-8 -*-
# Author:  Pablo Martí
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

__version__ = "$Rev: 1172 $"

from twisted.python import log
import serial
import vmc.common.exceptions as ex
from vmc.common.plugin import DBusDevicePlugin
from vmc.common.hardware.novatel import NovatelCustomizer
from vmc.common.statem.networkreg import NetworkRegStateMachine

from vmc.contrib.epsilon.modal import mode


class NovatelX950DNetworkRegStateMachine(NetworkRegStateMachine):
    """
    NetworkRegStateMachine for NovatelWireless' X950D
    
    The X950D doesn't seems to report via +CREG its network registration
    status, so the vanilla NetworkRegStateMachine wont work. Instead we
    shortcut the process and move directly to obtain_netinfo
    """
    wait_to_register = NetworkRegStateMachine.wait_to_register
    obtain_netinfo = NetworkRegStateMachine.obtain_netinfo
    search_operators = NetworkRegStateMachine.search_operators
    international_roaming = NetworkRegStateMachine.international_roaming
    register_with_operator = NetworkRegStateMachine.register_with_operator
    registration_finished = NetworkRegStateMachine.registration_finished
    registration_failed = NetworkRegStateMachine.registration_failed
    
    class check_registered(mode):
        def __enter__(self):
            pass
        def __exit__(self):
            pass
        
        def do_next(self):
            log.msg("%s: NEW MODE: check_registered" % self)
            self.device.sconn.set_charset("IRA")
            self.device.sconn.set_network_info_format() # set it to numeric
            
            def get_netinfo_cb(netinfo):
                # Novatel X950D doesn't reports +CREG notifications so we
                # have to modify its netreg process, we will query directly
                # the network is registered with
                log.msg("%s: NEW MODE: obtain_netinfo" % self)
                d = self.device.sconn.get_imsi()
                d.addCallback(lambda response: int(response[:5]))
                d.addCallback(self._process_imsi_cb)
            
            def get_netinfo_eb(failure):
                failure.trap(ex.NetworkTemporalyUnavailableError)
                d = self.device.sconn.get_netreg_status()
                d.addCallback(self._process_netreg_status)
                d.addErrback(log.err)
            
            d = self.device.sconn.get_network_info(process=False)
            d.addCallback(get_netinfo_cb)
            d.addErrback(get_netinfo_eb)

class NovatelX950DCustomizer(NovatelCustomizer):
    netrklass = NovatelX950DNetworkRegStateMachine


class NovatelX950D(DBusDevicePlugin):
    """L{vmc.common.plugin.DBusDevicePlugin} for Novatel's X950D"""
    name = "Novatel X950D"
    version = "0.1"
    author = u"Pablo Martí"
    custom = NovatelX950DCustomizer

    __remote_name__ = "Merlin X950D ExpressCard"

    __properties__ = {
        'usb_device.vendor_id' : [0x1410],
        'usb_device.product_id' : [0x1450],
    }

    def preprobe_init(self, ports, info):
        # Novatel secondary port needs to be flipped from DM to AT mode
        # before it will answer our AT queries. So the primary port
        # needs this string first or auto detection of ctrl port fails.
        # Note: Early models/firmware were DM only
        ser = serial.Serial(ports[0], timeout=1)
        ser.write('AT$NWDMAT=1\r\n')
        ser.close()

novatelx950d = NovatelX950D()