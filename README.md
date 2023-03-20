# sensor-network
Utilising raspberry pi pico W and the bme688 sensors a wireless sensor network sends data back to a mongoDB

# The Process
- The pico W just needs a power source, it will blink the onboard led 3 times with a successful network connection
- Each pico W makes POST requests to a listener service (which can running from within a Docker)
- The POST is validated and then added to a mongoDB

# Raspberry Pi Pico W
The pico W need to be flahsed with micropython. This can be done using [Thonny](https://thonny.org/).

It is dependent on a few packages that need installing on the pico W:
- picozero
- urequests
  - (this isn't an official micorpython package, however it is small and has no issues)

The [bme680.py](src/bme680.py) file needs to be saved into the `lib` folder on the pico W, and a `secrets.py` needs to be saved into the root directory of the pico W.

The `secrets.py` file should contain a dictionary called `secrets` with the following structure:
```
{ "ssid" : "NETOWRK_SSID",
  "pw"   : "NETOWRK_PASSWORD",
  "post_server"  : {"address" : "IP/URL_POST_SERVER",
                    "port"    : 12345,
                    "path"    : "/POST_ROUTE_PATH"},
  "mongo_server" : {"address" : "IP/URL_MONGO_SERVER",
                    "port"    : 98765}
}
```
The [pi_sensor.py](src/pi_sensor.py) file needs saving the the pico W root directory as `main.py` for it to run headless.

The BME688 sensor communicates using the I2C protocol with the SDI and SCK contacts connected to pins 4 and 5 respectively (GPIO2 and GPIO3). The sensor accepts 3-6V power. You can use either pin 36 (3V OUT) or 39 (VBUS -- the voltage here is passed through from the micro USB port).

# Miscellaneous
This repository is under active development.
