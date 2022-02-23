# UDI TUYA Poly_v2
This is a simple integration of TinyTuya to ISY994i only to Power On/Off Tuya WiFi smart bulbs/outlets.

Please install via [Polyglot v2](https://github.com/UniversalDevicesInc/polyglot-v2) Store.

[TinyTuya](https://pypi.org/project/tinytuya/) is a Python module to interface with Tuya WiFi smart devices.

### Custom parameter supported:
  - `devlist` - link to a YAML manifest of devices for Manual Discovery (ie. _devlist.yml_), no Automatic Discovery enabled.
  ```
     devices:
     - name: Bulb Name
       ip: 10.0.0.1
       ver: 3.3
       id: device_id
       key: device_key
       type: bulb (or oultet)
  ```
