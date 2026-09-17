# RS Solar

Home Assistant custom integration voor **RS Solar** energie-apparatuur.
Deze integratie leest data uit de lokale RS Solar API (Arduino-gebaseerd)
en toont onder andere:

- Firmware-versie
- Actieve voedingsbron (W)
- Actieve voeding gebruiker (W)
- Status voedingsbron
- Status voeding

## Vereisten

- Home Assistant **2024.1.0** of nieuwer
- Een RS Solar apparaat met actieve lokale API (`/api/v1/data`)

## Installatie via HACS

1. Ga naar **HACS** in Home Assistant.
2. Klik op **Meer** (≡) → **Aanvragen**.
3. Plak de repository-URL: `https://github.com/PancakeMaster-Productions/ha-rs-solar`
4. Selecteer **RS Solar** en klik op **Installeer**.
5. Start Home Assistant opnieuw op.
6. Ga naar **Instellingen › Apparaten & services** → **Nieuwe integratie toevoegen** → zoek **RS Solar**.
7. Voer de host, poort en poll-interval van uw apparaat in.

## Handmatige installatie

1. Clone deze repository of download de release.
2. Kopieer de map `custom_components/rs_solar` naar uw HA-configuratiemap:
   ```
   /config/custom_components/rs_solar
   ```
3. Start Home Assistant opnieuw op.
4. Voeg de integratie toe via **Instellingen › Apparaten & services**.

## Configuratie

| Veld | Omschrijving | Standaard |
|---|---|---|
| Host | IP-adres of hostname van het RS Solar apparaat | – |
| Poort | TCP-poort van de lokale API | `80` |
| Poll-interval | Interval in seconden waarmee de API wordt bevraagd (5–3600) | `30` |

## Ontwikkelen

```bash
git clone https://github.com/PancakeMaster-Productions/ha-rs-solar
cd ha-rs-solar
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # als u lokale dev-tooling wilt
```

De code gebruikt `aiohttp`, `voluptuous` en de standaard Home Assistant helpers.

## Licentie

[MIT](LICENSE)

## Credits

- Ontwikkeld door [PancakeMaster-Productions](https://github.com/PancakeMaster-Productions)
