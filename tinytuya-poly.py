#!/usr/bin/env python3
"""
TinyTuya NodeServer for UDI Polyglot v2
by Fernando Flechas (ferflechas)
"""
import polyinterface
import time
import sys
import tinytuya
from copy import deepcopy
import json
import yaml
from threading import Thread
from pathlib import Path
import math

LOGGER = polyinterface.LOGGER

with open('server.json') as data:
    SERVERDATA = json.load(data)
    data.close()
try:
    VERSION = SERVERDATA['credits'][0]['version']
except (KeyError, ValueError):
    LOGGER.info('Version not found in server.json.')
    VERSION = '0.0.0'

class Controller(polyinterface.Controller):
    def __init__(self, polyglot):
        super().__init__(polyglot)
        self.name = 'TUYA Controller'
        self.discovery_thread = None
        self.update_nodes = False
        self.devices_found = 0

    def start(self):
        LOGGER.info('Starting TinyTuya Polyglot v2 NodeServer version {}'.format(VERSION))
        self._checkProfile()
        self.discover()
        LOGGER.debug('Start complete')

    def stop(self):
        LOGGER.info('Stopping TinyTuya Polyglot v2 NodeServer version {}'.format(VERSION))

    def _checkProfile(self):
        profile_version_file = Path('profile/version.txt')
        if profile_version_file.is_file() and 'customData' in self.polyConfig:
            with profile_version_file.open() as f:
                profile_version = f.read().replace('\n', '')
                f.close()
            if 'prof_ver' in self.polyConfig['customData']:
                if self.polyConfig['customData']['prof_ver'] != profile_version:
                    self.update_nodes = True
            else:
                self.update_nodes = True
            if self.update_nodes:
                LOGGER.info('New Profile Version detected: {}, all nodes will be updated'.format(profile_version))
                cust_data = deepcopy(self.polyConfig['customData'])
                cust_data['prof_ver'] = profile_version
                self.saveCustomData(cust_data)
                self.updateNode(self)

    def shortPoll(self):
        if self.discovery_thread is not None:
            if self.discovery_thread.is_alive():
                LOGGER.debug('Skipping shortPoll() while discovery in progress...')
                return
            else:
                self.discovery_thread = None
        for node in self.nodes:
            self.nodes[node].update()

    def longPoll(self):
        if self.discovery_thread is not None:
            if self.discovery_thread.is_alive():
                LOGGER.debug('Skipping longPoll() while discovery in progress...')
                return
            else:
                self.discovery_thread = None
        for node in self.nodes:
            self.nodes[node].long_update()

    def update(self):
        pass

    def long_update(self):
        pass

    def discover(self, command=None):
        if self.discovery_thread is not None:
            if self.discovery_thread.is_alive():
                LOGGER.info('Discovery is still in progress')
                return
        self.discovery_thread = Thread(target=self._discovery_process)
        self.discovery_thread.start()

    def _manual_discovery(self):
        try:
            f = open(self.polyConfig['customParams']['devlist'])
        except Exception as ex:
            LOGGER.error('Failed to open {}: {}'.format(self.polyConfig['customParams']['devlist'], ex))
            return False
        try:
            data = yaml.safe_load(f.read())
            f.close()
        except Exception as ex:
            LOGGER.error('Failed to parse {} content: {}'.format(self.polyConfig['customParams']['devlist'], ex))
            return False

        if 'devices' not in data:
            LOGGER.error('Manual discovery file {} is missing devices section'.format(self.polyConfig['customParams']['devlist']))
            return False

        for d in data['devices']:
            name = d['name']
            id = d['id'][:14]
            if not id in self.nodes:
                self.devices_found += 1
                if d['type'] == 'bulb':
                    LOGGER.info('Found Bulb: {} ({})'.format(name, id))
                    self.addNode(Light(self, self.address, id, name, d), update = self.update_nodes)
                elif d['type'] == 'outlet':
                    LOGGER.info('Found Outlet: {} ({})'.format(name, id))
                    self.addNode(Light(self, self.address, id, name, d), update = self.update_nodes)
                else:
                    LOGGER.error('Unknown type: {}'.format(d['type']))
        self.setDriver('GV0', self.devices_found)
        return True

    def _discovery_process(self):
        LOGGER.info('Starting TUYA Discovery thread...')
        if 'devlist' in self.polyConfig['customParams']:
            LOGGER.info('Attempting manual discovery...')
            if self._manual_discovery():
                LOGGER.info('Manual discovery is complete')
                return
            else:
                LOGGER.error('Manual discovery failed')
        self.update_nodes = False
        try:
            old_devices_found = int(self.getDriver('GV0'))
        except:
            old_devices_found = self.devices_found
        else:
            if self.devices_found != old_devices_found:
                LOGGER.info('NOTICE: Device count {} is different, was {} previously'.format(self.devices_found, old_devices_found))
        self.setDriver('GV0', self.devices_found)
        LOGGER.info('TUYA Discovery thread is complete.')

    id = 'controller'
    drivers = [
                {'driver': 'ST', 'value': 1, 'uom': 2},
                {'driver': 'GV0', 'value': 0, 'uom': 56}
              ]
    commands = {
                'DISCOVER': discover
               }

class Light(polyinterface.Node):
    """
    TUYA Light Parent Class
    """
    def __init__(self, controller, primary, address, name, dev):
        super().__init__(controller, primary, address, name)
        self.tuya = None
        self.device = dev
        self.name = name
        self.last_status = None
        self.last_update = time.time()

    def start(self):
        self.update()
        self.long_update()

    def query(self, command = None):
        self.update()
        self.long_update()
        self.reportDrivers()

    def update(self):
        self.tuya = self._getTuya()
        self.setDriver('ST', self._getStatus())
        self.last_update = time.time()

    def long_update(self):
        self.last_update = time.time()

    def setOn(self, command):
        try:
            self.tuya = self._getTuya()
            if self.tuya is not None:
                self.tuya.set_status(True)
        except Exception as ex:
            LOGGER.error('Connection Error on setting {} device On. {}'.format(self.name, str(ex)))
        else:
            self.last_status = True
            self.setDriver('ST', 100)

    def setOff(self, command):
        try:
            self.tuya = self._getTuya()
            if self.tuya is not None:
                self.tuya.set_status(False)
        except Exception as ex:
            LOGGER.error('Connection Error on setting {} device Off. {}'.format(self.name, str(ex)))
        else:
            self.last_status = False
            self.setDriver('ST', 0)

    def _getTuya(self):
        if self.tuya is not None:
            return self.tuya
        _tuya = None
        try:
            if self.device['type'] == 'bulb':
                _tuya = tinytuya.BulbDevice(self.device['id'], self.device['ip'], self.device['key'])
            elif self.device['type'] == 'outlet':
                _tuya = tinytuya.OutletDevice(self.device['id'], self.device['ip'], self.device['key'])
        except Exception as ex:
            LOGGER.error('Error on {} device. {}'.format(self.name, str(ex)))
        if _tuya is not None:
            _tuya.set_version(self.device['ver'])
        return _tuya

    def _getStatus(self):
        _status = False
        if self.last_status is not None:
            _status = self.last_status
        if self.tuya is not None:
            try:
                _st = self.tuya.status()
                if 'dps' in _st:
                    if self.device['type'] == 'bulb':
                        _status = _st['dps']['20']
                    elif self.device['type'] == 'outlet':
                        _status = _st['dps']['1']
            except Exception as ex:
                LOGGER.error('Error on {} ({}) - {}. DPS: {}. Error {}'.format(self.name, self.device['type'], self.device['id'], _st, str(ex)))
            else:
                LOGGER.info('Status: {} on {} ({}) - {}. DPS: {}'.format(_status, self.name, self.device['type'], self.device['id'], _st))
        self.last_status = _status
        return 100 if _status else 0

    id = 'tuyalight'
    drivers = [
                 {'driver': 'ST', 'value': 0, 'uom': 51}
              ]
    commands = {
                 'DON': setOn,
                 'DOF': setOff,
                 'DFON': setOn,
                 'DFOF': setOff,
                 'QUERY': query
               }

if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('TinyTuya')
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
