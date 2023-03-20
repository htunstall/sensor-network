from secrets import secrets
from machine import Pin, I2C
from bme680  import *

import time
import network
import ntptime
import picozero
import urequests

#--------------------------------
# Settings
#--------------------------------
# Post Server
post_server = secrets["post_server"] # contains the keys: "address", "port", and "path" (in dict)

#--------------------------------
# Connect to the netowrk
#--------------------------------
print("Connecting to the netowrk `{}'".format(secrets["ssid"]))

# Set country to avoid possible errors
rp2.country("GB")

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(secrets["ssid"], secrets["pw"])

print("Waiting for connection", end="")
max_wait = 100
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >=3:
        break
    max_wait -= 1
    print(".", end="")
    time.sleep(1)
print()

# Handle connection error
if wlan.status() != 3:
    raise RuntimeError("Network connetion failed")

for i in range(wlan.status()):
    picozero.pico_led.on()
    time.sleep(0.3)
    picozero.pico_led.off()
    time.sleep(0.3)
print("Connected. WLAN Status: {}\nIP: {}\n".format(wlan.status(), wlan.ifconfig()[0]))

ntptime.settime()

#--------------------------------
# Sensor
#--------------------------------
print("Initilising sensor... ", end="")
i2c=I2C(1,sda=Pin(2), scl=Pin(3), freq=400000) # Initializing the I2C method
bme = BME680_I2C(i2c=i2c)
bme.sea_level_pressure = 1013.25 # in hPa
print("Done!")
   
#--------------------------------
# Logic loop
#--------------------------------
# The sensor takes 10.8 s to fully refresh all values
wait_time     = 15
    
# Program loop
picozero.pico_led.on() # Let the user all is running OK
while True:
    # Each rounded to sensor accuracy
    temp    = bme.temperature # +/- 0.5 [C]
    humi    = bme.humidity    # +/- 3 [%] (hysteresis +/- 1.5 %)
    pres    = bme.pressure    # +/- 1.9 Pa/K (0.12 Pa RMS Noise) [hPa | milibar]
    gas     = bme.gas         # [Ohms]
    timestr = "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(*time.localtime()[:6])
    
    # For Thonny debug
    print("{} | {:.1f} C | {:.0f} % | {:.2f} hPa (mb) | {} Ohms".format(timestr, temp, humi, pres, gas))
    
    #----------------------------
    # Make the POST request
    #----------------------------
    post_route = "http://{}:{}{}".format(post_server["address"], post_server["port"], post_server["path"])
    post_json  = {"time"        : timestr,
                  "temperature" : temp,
                  "pressure"    : pres,
                  "humidity"    : humi,
                  "gas"         : gas}

    try:
        r = urequests.post(post_route, json=post_json)
    except:
        print("Post request failed... Trying again")
        # Warn the user
        picozero.pico_led.off()
        continue

    # Validate the POST
    if r.status_code != 200:
        # Visually warn the user by flashing the onbard LED
        print("Error {}:\n{}\nTrying again in {} seconds".format(r.status_code, r.content.decode("utf-8"), err_wait_time))
        # Warn the user
        picozero.pico_led.off()
        continue
    else:
        # Stop warning the user
        picozero.pico_led.on()
    
    # Free up our little memory
    r.close()
    
    # Wait for the next 15 seconds before the next sensor reading
    time.sleep(wait_time)
