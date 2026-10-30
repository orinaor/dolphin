from datetime import timedelta

DOMAIN = "dolphin"
CONF_USERNAME = "Username"
CONF_PASSWORD = "Password"
UPDATE_INTERVAL = timedelta(seconds=30)
OFFLINE_NOTIFY_AFTER = timedelta(minutes=2)
PLATFORMS = ["switch", "sensor", "climate", "binary_sensor"]
