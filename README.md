# dht22-rpi

### pigpio and Python code (class Sensor) taken from http://abyz.me.uk/rpi/pigpio/index.html

### Notes

Tested on an RPi 4 4GB running Hypriot with an AM2032 sensor, YMMV. While this will compile on amd64/x86, pigpio will not run.

You'll need to bump `gpu_mem` in /config/boot.txt up past 16 MB in order for Docker to have enough to allocate; I used 64 MB.

If you get `initMboxBlock: init mbox zaps failed` and you've already raised the gpu_mem up, try restarting your Pi.

You also need to run it in privileged mode to get access to GPIO. If you know of a better way, please let me know.

### Build and run instructions

#### Python

`$ python DHT22.py`

#### Docker

`$ docker build -t $YOUR_TAG .`

or

`$ docker pull stephangarland/rpi-dht22:latest`

then

`$ docker run -d --privileged -v /path/on/host:/usr/src -e file='$FILENAME.log' $YOUR_TAG`



### Usage / Options

Args are below, defaults are as follows:

* temp: F
* interval: 300
* gpio: 5
* lower: 40
* upper: 100
* warn: True
* pushbullet: None

#### Python
```
$ python DHT22.py --help
usage: DHT22 [-h] [-t {C,F,K,R}] [-i INTERVAL] [-g GPIO] [-f FILE] [-l LOWER]
             [-u UPPER] [-w WARN] [-p PUSHBULLET]

Parse the output of a DHT22 sensor

optional arguments:
  -h, --help            show this help message and exit
  -t {C,F,K,R}, --temp {C,F,K,R}
                        Unit for temperature
  -i INTERVAL, --interval INTERVAL
                        Interval between logging in seconds
  -g GPIO, --gpio GPIO  GPIO pin sensor is connected to
  -f FILE, --file FILE  Path to logfile
  -l LOWER, --lower LOWER
                        Lower limit (F) to alert at
  -u UPPER, --upper UPPER
                        Upper limit (F) to alert at
  -w WARN, --warn WARN  Enable warnings in logs
  -p PUSHBULLET, --pushbullet PUSHBULLET
                        API key for Pushbullet
```

#### Docker

Pass desired long-form args from above as environment variables as seen in the run example, using `-e file=...`
