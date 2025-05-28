# eFriends for Home Assistant
Integrates measurements delivered by [eFriends](https://www.efriends.at) cube into Home Assistant.  
A descripton of the API can be found here [MeterDataAPI](https://support.efriends.at/hc/de/articles/26626854641181-Schnittstelle-Leistungsdaten) (in german)

At the moment the integration only supports reading the current power balance.  
If you want to see your energy consumption/generation you can use HA Integration helper.

## Installation
Copy the `custom_components/eFriendsHA` folder to the custom_components folder in your home-assistant config directory.

## Configuration
Add the sensor to your configuration.yaml file:
```yaml
  - platform: eFriendsHA
    ip: '<eFriends cube IP address'
    apikey: 'eFriends API key'
```
The API key can be generated in the API Manager in the eFriends Map webapp.