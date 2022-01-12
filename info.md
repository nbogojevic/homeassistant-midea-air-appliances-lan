[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]


![Midea Brands][logos]

_Adds support for Midea dehumidifer appliances via local network_

**This component will set up the following entities for dehumidifiers.**

Platform | Description
-- | --
`humidifier` | Dehumidifier entity. Depending on the model following modes are supported: `Set`, `Continuos`, `Smart` (_if supported_), `Dry` (_if supported_), `Antimould` (_if supported_), `Purifier` (_if supported_).
`fan` | Fan entity for controlling dehumidifier fan. Three preset modes are available: `Low`, `Medium` and `High`.
`binary_sensor` | Problem sensor indicating when tank is full.
`binary_sensor` | Problem sensor indicating when filter needs replacement (_disabled by default_).
`binary_sensor` | Cold sensor indicating defrosting is active (_disabled by default_).
`sensor` | Sensors for current relative humidity measured by dehumidifier.
`sensor` | Sensor for current temperature measured by dehumidifier.
`sensor` | Sensor for water level in the tank  (_enabled if device announces that water level is not 0% or 100%_).
`switch` | Switch ion mode on and off (_enabled if device announces that it is supported_)
`switch` | Switch pump on and off (_enabled if device announces that it is supported_)
`switch` | Switch sleep mode on and off (_disabled by default_)
`switch` | Switch to activate beep on action (_disabled by default_)


**This component will set up the following entities for air conditioners.**

Platform | Description
-- | --
`climate` | Climate entity.
`binary_sensor` | Problem sensor indicating when tank is full.
`binary_sensor` | Problem sensor indicating when filter needs replacement (_disabled by default_).
`binary_sensor` | Cold sensor indicating defrosting is active (_disabled by default_).
`sensor` | Sensor for outside temperature measured by air conditioner.
`switch` | Switch purifier mode on and off (_enabled if device announces that it is supported_)
`switch` | Switch dryer mode on and off (_disabled by default_)
`switch` | Switch sleep mode on and off (_disabled by default_)
`switch` | Switch to activate beep on action (_disabled by default_)
`switch` | Switch display to Fahrenheit degrees (_enabled if device announces that it is supported_)
`switch` | Switch turbo fan on and off (_enabled if device announces that it is supported_)
`switch` | Switch screen on and off (_enabled if device announces that it is supported_)

{% if not installed %}
## Installation

1. Click install.
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Midea Appliance (LAN)".

{% endif %}

## Configuration

[![Add Midea Appliance (LAN)][add-integration-badge]][add-integration]
* or search for "Midea Dehumidifier (LAN)"
![Search for "Midea Appliance (LAN)"](https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/raw/main/assets/setup-choice.png)
* Sign-in with Midea app account - you may choose Midea app that corresponds to one you use (anyone should work).
![Setup midea App account"](https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/raw/main/assets/setup-account.png)
* On advanced options dialog you may enter another application key if you want, specify a network range to be used for discovery or choose to rely on cloud polling. If you don't specify network range, the integration will scan all local network interfaces.
![Advanced options"](https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/raw/main/assets/advanced-options.png)
* For devices that are known to cloud service, but not discovered localy, you will have another prompt to enter details if you know them or to specify that you want to rely on cloud polling for that device.
![Advanced options"](https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/raw/main/assets/appliance-missing.png)


***

## UI

You may look at following Lovelace cards:

https://github.com/MiguelCosta/Dehumidifier_Comfee_Card

https://github.com/sicknesz/midea-inventor-card


[commits-shield]: https://img.shields.io/github/commit-activity/y/nbogojevic/midea-dehumidifier-lan.svg?style=for-the-badge
[commits]: https://github.com/nbogojevic/midea-dehumidifier-lan/commits/master
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license]: https://github.com/nbogojevic/midea-dehumidifier-lan/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/nbogojevic/midea-dehumidifier-lan.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Nenad%20Bogojević-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/nbogojevic/midea-dehumidifier-lan.svg?style=for-the-badge
[releases]: https://github.com/nbogojevic/midea-dehumidifier-lan/releases

[user_profile]: https://github.com/nbogojevic
[logos]: https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/raw/main/assets/logos.png
[add-integration]: https://my.home-assistant.io/redirect/config_flow_start?domain=midea_dehumidifier_lan
[add-integration-badge]: https://my.home-assistant.io/badges/config_flow_start.svg

[dehumidifier-details]: https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/raw/main/assets/dehumidifier-details.png
