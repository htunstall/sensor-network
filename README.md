# sensor-network
Utilising raspberry pi pico W and the bme688 sensors a wireless sensor network sends data back to a mongoDB

# The Process
- The pico W just needs a power source, it will blink the onboard led 3 times with a successful network connection
- Each pico W makes POST requests to a listener service (which can running from within a Docker)
- The POST is validated and then added to a mongoDB

This repository is under active development
