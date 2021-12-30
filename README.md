This custom component for Home assistant adds support for Midea dehumidifier appliances via the local area network.

# homeassistant-midea-dehumidifier-lan

[![Repository validation](https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/actions/workflows/validate.yml/badge.svg)](https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/actions/workflows/validate.yml)

[![hacs][hacsbadge]][hacs]
[![GitHub Release][releases-shield]][releases]

Home Assistant custom component for controlling Midea dehumidifieres on local network.

## Installation instruction

### HACS
The easiest way to install the this integration is with [HACS](https://hacs.xyz/). First, install [HACS](https://hacs.xyz/docs/setup/download) if you don't have it yet. In Home Assistant, go to `HACS -> Integrations`, click on `+ Explore & Download Repositories`, search for `Midea Dehumidifier (LAN)`, and click download.

Once the integration is installed, you can add it to the Home Assistant by going to `Configuration -> Devices & Services`, clicking `+ Add Integration` and searching for `Midea Dehumidifier (LAN)` or, using My Home Assistant service, you can click on:

[![Add Midea Dehumidifier (LAN)][add-integration-badge]][add-integration]

### Manual installation
1. Update Home Assistant to version 2021.12 or newer.
2. Clone this repository.
3. Copy the `custom_components/midea_dehumidifier_lan` folder into your Home Assistant's `custom_components` folder.

### Configuring
1. Add `Midea Dehumidifer (LAN)` integration via UI.
2. Enter Midea cloud username and password. Those are the same used in NetHome Plus mobile application.
3. The integration will discover dehumidifiers on local network(s).
4. If a dehumidifer is not automatically discovered, but is registered to the cloud account, user is prompted to enter IPv4 address of the dehumidifier.

## Known issues

* If IPv4 address of dehumidifer changes, new IPv4 address will not be used until Home Assistant's restart.
* If Home Assistant installation doesn't have access to physical network, the integration may not discover all appliances.
* Dehumidifier modes correspond to Inventor EVA ΙΟΝ Pro Wi-Fi model. Your dehumidifer might use different names (e.g. Boost instead of Dry)
* Having two integrations accessing the same device can result in undefined behavior. For example, having two Home Assistant instances accessing same device, or using one of other Midea dehumidifier integrations in combination with this one. To avoid problems use a single integration - this one :).
* If you encounter issues after upgrading, uninstall the integration, restart Home Assistant and re-install it.
* Some of sensors and switches are disabled by default. You need to enable them manually. See table below for more information.
* Temperature sensor is usually under-reporting real ambient temperature. This may be due to proximity to cooling pipes of the humidifier, algorithm or electronics error. The under-reporting depends on the active mode, and higher modes may result in larger offset from real temperature.

## Supported entities

This custom component creates following entites for each discovered dehumidifer:

Platform | Description
-- | --
`humidifier` | Dehumidifier entity. Depending on the model following modes are supported: `Set`, `Continous`, `Smart` (_if supported_), `Dry` (_if supported_), `Antimould` (_if supported_), `Purifier` (_if supported_).
`fan` | Fan entity for controlling dehumidifer fan. Depending on model there may be one, two or three preset modes. When three preset modes are available, they are `Silent`, `Medium` and `Turbo`. When three preset modes are supported, they are `Low` and `High`. When a single preset exists, it is `Auto`. Switching fan off sets `Silent` or `Low` preset and switching on sets `Medium` or `High` reset.
`binary_sensor` | Problem sensor indicating when tank is full.
`binary_sensor` | Problem sensor indicating when filter needs replacement (_disabled by default_).
`binary_sensor` | Cold sensor indicating defrosting is active (_disabled by default_).
`sensor` | Sensors for current relative humidity measured by dehumidifier.
`sensor` | Sensor for current temperature measured by dehumidifier.
`switch` | Switch ION mode on and off (_enabled if device announces that it is supported_)
`switch` | Switch pump on and off (_enabled if device announces that it is supported_)
`switch` | Switch sleep mode on and off (_disabled by default_)
`switch` | Switch to activate beep on action (_disabled by default_)

## See also

https://github.com/nbogojevic/midea-beautiful-dehumidifier

[add-integration]: https://my.home-assistant.io/redirect/config_flow_start?domain=midea_dehumidifier_lan
[add-integration-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat
[maintenance-shield]: https://img.shields.io/badge/maintainer-Nenad%20Bogojević-blue.svg?style=flat
[releases-shield]: https://img.shields.io/github/release/nbogojevic/homeassistant-midea-dehumidifier-lan.svg?style=flat
[releases]: https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/releases