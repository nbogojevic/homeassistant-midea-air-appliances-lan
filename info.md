[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]


![Midea Brands][logos]

_Adds support for Midea dehumidifer appliances via local network_

**This component will set up the following platforms.**

Platform | Description
-- | --
`humidifier` | Dehumidifier entity.
`fan` | Fan entity for controlling dehumidifer fan.
`binary_sensor` | Problem sensor active when tank is full.
`sensor` | Current relative humidity measured by dehumidifier.
`switch` | Switch ION mode on and off if supported by dehumidifier




{% if not installed %}
## Installation

1. Click install.
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Midea Dehumidifier (LAN)".

{% endif %}


## Configuration is done in the UI

<!---->

***

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
[logos]: assets/logos.png