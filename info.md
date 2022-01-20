{% if prerelease %}
# This is a pre-release version!
---
{% endif %}

{% if installed %}
## Changes as compared to your installed version:

{% if (version_installed.split(".")[0] | int) < 0 %}
{% if (version_installed.split(".")[1] | int) < 6 %}

## Breaking Changes
- Unique id of entities changed. Using serial number now instead of cloud API id.
- Removed sleep switch.

## Major changes
- Added support for air conditioners (**beta**)
- Added periodic discovery of appliances.
- Added support for appliance address change.
- Enable integration configuration.
- Enable discovery of appliances at later time
- Select appliance discovery behavior via dropdown
- Add notification if appliance is discovered on the network, but was either ignored, or polled from the cloud
- Added tank removed (bucket) binary sensor
- Reverted to three presets for fan in all cases.

## Bug fixes
- If appliance doesn't load at start, integration will attempt again to set it up.
- An error during startup doesn't prevent integration to load.
- Fixed integration reload failing.
- Fixed entity naming conflicts after an appliance with same id as another old appliance is added.

{% endif %}
{% endif %}
{% endif %}

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]


![Midea Brands][logos]

_Adds support for Midea air conditioning and dehumidifier appliances via local network. Support for air condioning devices is in **beta**_

**This component will set up the following entities for dehumidifiers.**

Platform | Description
-- | --
`humidifier` | Dehumidifier entity. Depending on the model following modes are supported: `Set`, `Continuos`, `Smart` (_if supported_), `Dry` (_if supported_), `Antimould` (_if supported_), `Purifier` (_if supported_).
`fan` | Fan entity for controlling dehumidifier fan. Three preset modes are available: `Low`, `Medium` and `High`.
`binary_sensor` | Problem sensor indicating when tank is full.
`binary_sensor` | Problem sensor indicating when tank is removed (_created if device announces that pump is supported_).
`binary_sensor` | Problem sensor indicating when filter needs cleaning (_created if device announces that filter is supported_).
`binary_sensor` | Cold sensor indicating defrosting is active (_disabled by default_).
`sensor` | Sensors for current relative humidity measured by dehumidifier.
`sensor` | Sensor for current temperature measured by dehumidifier.
`sensor` | Sensor for water level in the tank (_created if device announces that water level is supported_).
`sensor` | Sensor with value of error code of the appliance (_disabled by default_).
`switch` | Switch ion mode on and off (_created if device announces that (an)ion mode is supported_).
`switch` | Switch pump on and off (_created if device announces that pump is supported_).
`switch` | Switch to activate beep on action (_disabled by default_).


**This component will set up the following entities for air conditioners.**

Platform | Description
-- | --
`climate` | Climate entity.
`binary_sensor` | Problem sensor indicating when tank is full.
`binary_sensor` | Problem sensor indicating when filter needs replacement (_disabled by default_).
`binary_sensor` | Cold sensor indicating defrosting is active (_disabled by default_).
`sensor` | Sensor for outside temperature measured by air conditioner.
`sensor` | Sensor with value of error code of the appliance (_disabled by default_).
`switch` | Switch purifier mode on and off (_enabled if device announces that it is supported_).
`switch` | Switch dryer mode on and off (_disabled by default_).
`switch` | Switch sleep mode on and off (_disabled by default_).
`switch` | Switch to activate beep on action (_disabled by default_).
`switch` | Switch display to Fahrenheit degrees (_enabled if device announces that it is supported_).
`switch` | Switch turbo fan on and off (_enabled if device announces that it is supported_).
`switch` | Switch screen on and off (_enabled if device announces that it is supported_).

{% if not installed %}
## Installation

1. Click Install.
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Midea Air Appliances (LAN)".

{% endif %}

## Configuration

[![Add Midea Air Appliances (LAN)][add-integration-badge]][add-integration]
* or search for "Midea Air Appliances (LAN)"
![Search for "Midea Air Appliances (LAN)"](https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/raw/main/assets/setup-choice.png)
* Sign-in with Midea app account - you may choose Midea app that corresponds to one you use (anyone should work).
![Setup Midea App account"](https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/raw/main/assets/setup-account.png)
* On advanced options dialog you may enter another application key if you want, specify a network range to be used for discovery or choose to rely on cloud polling. If you don't specify network range, the integration will scan all local network interfaces.
![Advanced options"](https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/raw/main/assets/advanced-options.png)
* For devices that are known to cloud service, but not discovered locally, you will have another prompt to enter details if you know them or to specify that you want to rely on cloud polling for that device.
![Advanced options"](https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/raw/main/assets/appliance-missing.png)


***

## UI

You may look at following Lovelace cards:

https://github.com/MiguelCosta/Dehumidifier_Comfee_Card

https://github.com/sicknesz/midea-inventor-card


[commits-shield]: https://img.shields.io/github/commit-activity/y/nbogojevic/midea-dehumidifier-lan.svg?style=for-the-badge
[commits]: https://github.com/nbogojevic/midea-dehumidifier-lan/commits/master
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license]: https://github.com/nbogojevic/midea-dehumidifier-lan/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/nbogojevic/midea-dehumidifier-lan.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Nenad%20Bogojević-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/nbogojevic/midea-dehumidifier-lan.svg?style=for-the-badge
[releases]: https://github.com/nbogojevic/midea-dehumidifier-lan/releases

[user_profile]: https://github.com/nbogojevic
[logos]: https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/raw/main/assets/logos.png
[add-integration]: https://my.home-assistant.io/redirect/config_flow_start?domain=midea_dehumidifier_lan
[add-integration-badge]: https://my.home-assistant.io/badges/config_flow_start.svg

[dehumidifier-details]: https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/raw/main/assets/dehumidifier-details.png
