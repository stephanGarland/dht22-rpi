# dht22-rpi

### pigpio and Python code taken from http://abyz.me.uk/rpi/pigpio/index.html

### Notes

Tested on an RPi 4 4GB running Hypriot with an AM2032 sensor, YMMV

You'll need to bump `gpu_mem` in /config/boot.txt up past 16 MB in order for Docker to have enough to allocate; I used 64 MB.

You also need to run it in privileged mode to get access to GPIO. If you know of a better way, please let me know.

Not on Dockerhub yet, so clone this onto your Pi and build it.

### Build and run instructions

$ docker build -t $YOUR_TAG .

$ docker run --privileged $YOUR_TAG
