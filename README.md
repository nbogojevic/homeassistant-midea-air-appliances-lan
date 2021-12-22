This custom component for Home assistant adds support for Midea dehumidifier appliances via the local area network.

# homeassistant-midea-dehumidifier-lan

[![Repository validation](https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/actions/workflows/validate.yml/badge.svg)](https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/actions/workflows/validate.yml)

Home Assistant custom component for controlling Midea dehumidiferes on local network

## Installation instruction

### HACS
Add this repository as custom integration repository to HACS.

### Manual
1. Update Home Assistant to version 2021.12 or newer
2. Clone this repository
3. Copy the `custom_components/midea_dehumidifier_lan` folder into your Home Assistant's `custom_components` folder

### Configuring
1. Add `Midea Dehumidifer (LAN)` integration via UI
2. Enter Midea cloud username and password. Those are the same used in NetHome Plus mobile application.
3. The integration will discover dehumidifiers on local network(s).
4. If a dehumidifer is not automatically discovered, but is registered to the cloud account, user is prompted to enter IPv4 address of the dehumidifier.

## Known issues

* If IPv4 address of dehumidifer changes, new IPv4 address will not be used until Home Assistant's restart.


## Supported entities

This custom component creates following entites for each discovered dehumidifer:

* humidifier/dehumidifer
* fan
* sensor with current environment humidity
* sensor with current environment temperature
* binary sensor for full tank
* switch for controlling ION mode (switch has no effect if dehumidifier doesn't support it)

## See also

https://github.com/nbogojevic/midea-beautiful-dehumidifier
