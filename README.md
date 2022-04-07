This custom component for Home Assistant adds support for Midea air conditioner and dehumidifier appliances via the local area network.

# homeassistant-midea-air-appliances-lan

[![Repository validation](https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/actions/workflows/validate.yml/badge.svg)](https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/actions/workflows/validate.yml)

[![hacs][hacsbadge]][hacs]
[![GitHub Release][releases-shield]][releases]

Home Assistant custom component for controlling Midea appliance on local network.

## Installation instruction

### HACS
The easiest way to install this integration is with [HACS][hacs]. First, install [HACS][hacs-download] if you don't have it yet. In Home Assistant, go to `HACS -> Integrations`, click on `+ Explore & Download Repositories`, search for `Midea Air Appliances (LAN)`, and click download. After download, restart Home Assistant.

Once the integration is installed, you can add it to the Home Assistant by going to `Configuration -> Devices & Services`, clicking `+ Add Integration` and searching for `Midea Air Appliances (LAN)` or, using My Home Assistant service, you can click on:

[![Add Midea Air Appliances (LAN)][add-integration-badge]][add-integration]

### Manual installation
1. Update Home Assistant to version 2021.12 or newer.
2. Clone this repository.
3. Copy the `custom_components/midea_dehumidifier_lan` folder into your Home Assistant's `custom_components` folder.

### Configuring
1. Add `Midea Air Appliances (LAN)` integration via UI.
2. Enter Midea cloud username and password and select mobile application you use.
3. The integration will discover appliance on local network(s).
4. If an appliance is not automatically discovered, but is registered to the cloud account, user is prompted to enter IPv4 address of the appliance.
5. If you want to use integration with air conditioner unit(s), please select the checkbox on `Advanced settings` page.

## Known issues

* If IPv4 address of appliance changes, new IPv4 address will not be used until Home Assistant's restart.
* If Home Assistant installation doesn't have access to physical network, the integration may not discover all appliances.
* Dehumidifier modes correspond to Inventor EVA ΙΟΝ Pro Wi-Fi model. Your dehumidifier might use different names (e.g., `Boost` instead of `Dry`)
* Having two integrations accessing the same device can result in undefined behavior. For example, having two Home Assistant instances accessing same device, or using one of other Midea appliance integrations in combination with this one. To avoid problems, use a single integration - this one 🙂.
* If you encounter issues after upgrading, uninstall the integration, restart Home Assistant and re-install it.
* Some of sensors and switches are disabled by default. You need to enable them manually. See tables below for more information.
* Temperature sensor on dehumidifier is often under-reporting real ambient temperature. This may be due to sensor proximity to cooling pipes of the humidifier, algorithm, or electronics error. The under-reporting depends on the active mode, and stronger modes may result in larger offset from real temperature.
* Some Midea appliances, built in 2021 and later, use Tuya based patform and this integration will not work with them. In some cases those appliances have have same model names as old ones.
* When migrating from version 0.6 or 0.7 to 0.8, integration may fail. Please remove and re-install integration.

## Supported appliances

* Comfee MDDF-16DEN7-WF or MDDF-20DEN7-WF (tested with 20L version)
* Inventor EVA ΙΟΝ Pro Wi-Fi (EP3-WiFi 16L/20L) (tested with 20L version)
* Inventor Eva II Pro Wi-Fi (EVP-WF16L/20L)
* Pro Breeze 30L Smart Dehumidifier with Wifi / App Control
* Midea SmartDry dehumidifiers (22, 35, 50 pint models)
* Midea Cube dehumidifiers (20, 35, 50 pint models)

Supported are V3 and V2 protocols that allow local network access. V3 protocol requires one connection to Midea cloud to get token and key needed for local network access. Some old models use V1 XML based protocol which is not supported. Some newer models use Tuya protocol.

## Supported entities

This custom component creates following entities for each discovered dehumidifier:

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
`switch` | Switch ion mode on and off (_created if device announces that (an)ion mode is supported_)
`switch` | Switch pump on and off (_created if device announces that pump is supported_).
`switch` | Switch to enable pump (_created if device announces that pump is supported_).
`switch` | Switch to activate beep on action (_disabled by default_).


In addition to this, `humidifier` entity will have additonal attributes describing capabilities, current and last error code, time of last error, as well as last payloads received.

This custom component creates following entities for each discovered air conditioner:

Platform | Description
-- | --
`climate` | Climate entity.
`sensor` | Sensor for outside temperature measured by air conditioner.
`switch` | Switch purifier mode on and off (_enabled if device announces that it is supported_).
`switch` | Switch dryer mode on and off (_disabled by default_).
`switch` | Switch to activate beep on action (_disabled by default_).
`switch` | Switch display to Fahrenheit degrees (_enabled if device announces that it is supported_).
`switch` | Switch turbo fan on and off (_enabled if device announces that it is supported_).
`switch` | Switch screen on and off (_enabled if device announces that it is supported_).

In addition to this, `climate` entity will have additonal attributes describing capabilities, current and last error code, time of last error, as well as last payloads received.

## Troubleshooting

If there are problems while using integration setup, an advanced debug logging can be activated via `Advanced settings` page.

Once activated, logs can be see by clicking at:

Select `Load Full Home Assistant Log` to see all debug mode logs. Please include as much logs as possible if you open an [issue](https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/issues/new?assignees=&labels=&template=issue.md).

[![Home Assistant Logs][ha-logs-badge]][ha-logs]

Debug logging can be activated without going through setup process:

[![Logging service][ha-service-badge]][ha-service]

On entry page, paste following content:

```yaml
service: logger.set_level
data:
    custom_components.midea_dehumidifier_lan: DEBUG
    midea_beautiful: DEBUG
```

It is possible to activate debug logging on Home Assistent start. To do this, open Home Assistant's `configuration.yaml` file on your machine, and add following to `logger` configuration:

```yaml
logger:
  # Begging of lines to add
  logs:
    custom_components.midea_dehumidifier_lan: debug
    midea_beautiful: debug
  # End of lines to add
```

Home Assistant needs to be restarted after this change.


## See also

https://github.com/nbogojevic/midea-beautiful-air

### UI

Following Lovelace cards work well with this integration:

https://github.com/MiguelCosta/Dehumidifier_Comfee_Card

https://github.com/sicknesz/midea-inventor-card

## Notice

Midea, Inventor, Comfee', Pro Breeze, and other names are trademarks of their respective owners.

[add-integration]: https://my.home-assistant.io/redirect/config_flow_start?domain=midea_dehumidifier_lan
[add-integration-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
[hacs]: https://hacs.xyz
[hacs-download]: https://hacs.xyz/docs/setup/download
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg?style=flat
[ha-logs]: https://my.home-assistant.io/redirect/logs
[ha-logs-badge]: https://my.home-assistant.io/badges/logs.svg
[ha-service]: https://my.home-assistant.io/redirect/developer_call_service/?service=logger.set_level
[ha-service-badge]: https://my.home-assistant.io/badges/developer_call_service.svg
[maintenance-shield]: https://img.shields.io/badge/maintainer-Nenad%20Bogojević-blue.svg?style=flat
[releases-shield]: https://img.shields.io/github/release/nbogojevic/homeassistant-midea-air-appliances-lan.svg?style=flat
[releases]: https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/releases