# RS Solar

Home Assistant custom integration for **RS Solar** energy equipment.
This integration reads data from the local RS Solar API
and displays, among other things:

- Firmware version
- Active power source (W)
- Active user power (W)
- Power source status
- User power status
- State

It also exposes a **Charge Block** switch to control the RS Solar state endpoint:

- `state = 0` → Normal
- `state = 1` → Charge Block

## Requirements

- Home Assistant **2024.1.0** or newer
- An RS Solar device with an active local API:
  - `/api/v1/data`
  - `/api/v1/state`

## Installation via HACS

1. Go to **HACS** in Home Assistant.
2. Click **More** (≡) → **Add**.
3. Paste the repository URL: `https://github.com/PancakeMaster-Productions/ha-rs-solar`
4. Select **RS Solar** and click **Install**.
5. Restart Home Assistant.
6. Go to **Settings › Devices & Services** → **Add Integration** → search for **RS Solar**.
7. Enter the host, port and poll interval of your device.

## Manual installation

1. Clone this repository or download the release.
2. Copy the `custom_components/rs_solar` folder to your HA configuration directory:
   ```
   /config/custom_components/rs_solar
   ```
3. Restart Home Assistant.
4. Add the integration via **Settings › Devices & Services**.

## Entities

| Entity              | Type   | Description                                             |
|---------------------|--------|---------------------------------------------------------|
| State               | Sensor | Shows the current RS Solar state: Normal / Charge Block |
| Charge Block        | Switch | Controls the RS Solar state endpoint                    |
| Firmware Version    | Sensor | Shows the firmware version                              |
| Active Power Source | Sensor | Shows active power source in watts                      |
| Active Power User   | Sensor | Shows active user power in watts                        |
| Power Source Status | Sensor | Shows the power source status                           |
| Power User Status   | Sensor | Shows the user power status                             |

## Configuration

| Field         | Description                                             | Default |
|---------------|---------------------------------------------------------|---------|
| Host          | IP address or hostname of the RS Solar device           | –       |
| Port          | TCP port of the local API                               | `80`    |
| Poll interval | Interval in seconds at which the API is polled (5–3600) | `30`    |

## Development

```bash
git clone https://github.com/PancakeMaster-Productions/ha-rs-solar
cd ha-rs-solar
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # if you want local dev tooling
```

The code uses `aiohttp`, `voluptuous` and the standard Home Assistant helpers.

## License

[MIT](LICENSE)

## Credits

- Developed by [PancakeMaster-Productions](https://github.com/PancakeMaster-Productions)

