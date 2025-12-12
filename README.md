# eFriends for Home Assistant
Integrates measurements delivered by [eFriends](https://www.efriends.at) cube into Home Assistant.
A descripton of the API can be found here [MeterDataAPI](https://support.efriends.at/hc/de/articles/26626854641181-Schnittstelle-Leistungsdaten) (in german)

The integration adds five sensors:
* Power: current power value. Positiv if power is consumed and negativ if power is feed in.
* PowerFromGrid: currently consumed power
* PowerToGrid: currently feed in power
* EnergyFromGrid: accumulated consumed energy
* EnergyToGrid: acucumulated feed in energy

## Installation
### HACS
Add this repository as user-defined repository to HACS. Search for eFriends integration and install
### Manual
Copy the `custom_components/eFriendsHA` folder to the custom_components folder in your home-assistant config directory.

## Configuration
Add the sensor to your configuration.yaml file:
```yaml
  - platform: eFriendsHA
    ip: '<eFriends cube IP address'
    apikey: 'eFriends API key'
```
The API key can be generated in the API Manager in the eFriends Map webapp.