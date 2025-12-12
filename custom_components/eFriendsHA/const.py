"""Constants"""
DOMAIN = "eFriendsHA"

LOCAL_BASE_URL = "http://{}/v3/MeterDataAPI/{}?apiKey={}"
REMOTE_BASE_URL = "https://{}.balena-devices.com/v3/MeterDataAPI/{}?apiKey={}"

NAME_POWER = "Power"
NAME_P_FROMGRID = "PowerFromGrid"
NAME_P_TOGRID = "PowerToGrid"
NAME_E_FROMGRID = "EnergyFromGrid"
NAME_E_TOGRID = "EnergyToGrid"
CMD_POWER = "getCurrentValue"