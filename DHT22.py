#!/usr/bin/python
# -*- coding: utf-8 -*-

# From https://github.com/joan2937/pigpio/tree/master/EXAMPLES/Python/DHT22_AM2302_SENSOR

import argparse
import atexit
import logging
import os
import time

from pushbullet import Pushbullet
from typing import NamedTuple

import pigpio

# Thank you to u/chepner: https://stackoverflow.com/a/18700817/4221094
class MinTempArg(argparse.Action):


    """
    Better workaround than the custom type to set minimum polling interval
    """

    def __call__(self, parser, namespace, values, option_string=None):
        if values < 3:
            parser.error('Minimum polling interval is 3 for DHT22 stability'.format(option_string))
        setattr(namespace, self.dest, values)


class Docker(NamedTuple):

    """
    Retrieves named environment variables passed in from the user
    and applies their values to variables to be passed for args.
    If absent, the second argument to os.getenv() is used as a default.
    Note that file MUST be specified.
    """
    temp:       str = os.getenv('temp', 'F')
    interval:   int = int(os.getenv('interval', 300))
    gpio:       int = int(os.getenv('gpio', 5))
    file:       str = os.getenv('file')
    lower:      int = int(os.getenv('lower', 40))
    upper:      int = int(os.getenv('upper', 100))
    warn:       bool = os.getenv('warn', True)
    pushbullet: str = os.getenv('pushbullet', None)


class Setup:


    """
    Sets up args and logging capabilities
    """

    def make_args(self):
        parser = argparse.ArgumentParser(
            prog='DHT22',
            description='Parse the output of a DHT22 sensor'
        )

        parser.add_argument(
            '-t',
            '--temp',
            default='F',
            choices=['C', 'F', 'K', 'R'],
            type=str,
            help='Unit for temperature',
        )

        parser.add_argument(
            '-i',
            '--interval',
            action=MinTempArg,
            default=300,
            type=int,
            help='Interval between logging in seconds'
        )

        parser.add_argument(
            '-g',
            '--gpio',
            default=5,
            type=int,
            help='GPIO pin sensor is connected to'
        )

        parser.add_argument(
            '-f',
            '--file',
            type=str,
            help='Path to logfile'
        )

        parser.add_argument(
            '-l',
            '--lower',
            type=int,
            default=40,
            help='Lower limit (F) to alert at'
        )

        parser.add_argument(
            '-u',
            '--upper',
            type=int,
            default=100,
            help='Upper limit (F) to alert at'
        )

        parser.add_argument(
            '-w',
            '--warn',
            type=bool,
            default=True,
            help='Enable warnings in logs'
        )

        parser.add_argument(
            '-p',
            '--pushbullet',
            type=str,
            default=None,
            help='API key for Pushbullet'
        )

        return parser.parse_args()

    
    def setup_logger(self, logfile):
        logger = logging.getLogger('server_room_temp')
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%Y-%m-%d %H:%M:%S')

        if logfile:
            file_handler = logging.FileHandler(logfile)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        else:
            stdout_handler = logging.StreamHandler()
            stdout_handler.setLevel(logging.DEBUG)
            stdout_handler.setFormatter(formatter)
            logger.addHandler(stdout_handler)

        return logger

    def write_log(self, logger, warn, temp, humidity, upper, lower, pushbullet):
        if (warn and (temp > upper) or (temp < lower)):
            logger.warning('Temp: {:0.1f} Humidity: {:0.1f}%'.format(temp, humidity))
            if pushbullet:
                try: 
                    pb = Pushbullet(pushbullet)
                    pb.push_note('Warning', 'Temp: {:0.1f} Humidity: {:0.1f}%'.format(temp, humidity))
                except InvalidKeyError:
                    logger.error('Invalid Pushbullet API key')
        else:
            logger.info('Temp: {:0.1f} Humidity: {:0.1f}%'.format(temp, humidity))

class Sensor:


    """
    A class to read relative humidity and temperature from the
    DHT22 sensor.  The sensor is also known as the AM2302.

    The sensor can be powered from the Pi 3V3 or the Pi 5V rail.

    Powering from the 3V3 rail is simpler and safer.  You may need
    to power from 5V if the sensor is connected via a long cable.

    For 3V3 operation connect pin 1 to 3V3 and pin 4 to ground.

    Connect pin 2 to a gpio.

    For 5V operation connect pin 1 to 5V and pin 4 to ground.

    The following pin 2 connection works for me.  Use at YOUR OWN RISK.

    5V--5K_resistor--+--10K_resistor--Ground
                        |
    DHT22 pin 2 -----+
                        |
    gpio ------------+
    """

    def __init__(self, pi, gpio, LED=None, power=None):
        """
        Instantiate with the Pi and gpio to which the DHT22 output
        pin is connected.

        Optionally a LED may be specified.  This will be blinked for
        each successful reading.

        Optionally a gpio used to power the sensor may be specified.
        This gpio will be set high to power the sensor.  If the sensor
        locks it will be power cycled to restart the readings.

        Taking readings more often than about once every two seconds will
        eventually cause the DHT22 to hang.  A 3 second interval seems OK.
        """

        self.pi = pi
        self.gpio = gpio
        self.LED = LED
        self.power = power

        if power is not None:
            pi.write(power, 1)  # Switch sensor on.
            time.sleep(2)

        self.powered = True

        self.cb = None

        atexit.register(self.cancel)

        self.bad_CS = 0  # Bad checksum count.
        self.bad_SM = 0  # Short message count.
        self.bad_MM = 0  # Missing message count.
        self.bad_SR = 0  # Sensor reset count.

        # Power cycle if timeout > MAX_TIMEOUTS.

        self.no_response = 0
        self.MAX_NO_RESPONSE = 2

        self.rhum = -999
        self.temp = -999

        self.tov = None

        self.high_tick = 0
        self.bit = 40

        pi.set_pull_up_down(gpio, pigpio.PUD_OFF)

        pi.set_watchdog(gpio, 0)  # Kill any watchdogs.

        self.cb = pi.callback(gpio, pigpio.EITHER_EDGE, self._cb)

    def _cb(self, gpio, level, tick,):
        # Accumulate the 40 data bits.  Format into 5 bytes, humidity high,
        # humidity low, temperature high, temperature low, checksum.

        diff = pigpio.tickDiff(self.high_tick, tick)

        if level == 0:
            # Edge length determines if bit is 1 or 0.
            if diff >= 50:
                val = 1
                if diff >= 200:  # Bad bit?
                    self.CS = 256  # Force bad checksum.
            else:
                val = 0

            if self.bit >= 40:  # Message complete.
                self.bit = 40
            elif self.bit >= 32:
                # In checksum byte.
                self.CS = (self.CS << 1) + val
                if self.bit == 39:
                    # 40th bit received.
                    self.pi.set_watchdog(self.gpio, 0)
                    self.no_response = 0
                    total = self.hH + self.hL + self.tH + self.tL

                    if total & 255 == self.CS:  # Is checksum ok?
                        self.rhum = ((self.hH << 8) + self.hL) * 0.1
                        if self.tH & 128:  # Negative temperature.
                            mult = -0.1
                            self.tH = self.tH & 127
                        else:
                            mult = 0.1

                        self.temp = ((self.tH << 8) + self.tL) * mult
                        self.tov = time.time()

                        if self.LED is not None:
                            self.pi.write(self.LED, 0)

                    else:
                        self.bad_CS += 1

            elif self.bit >= 24:
                # in temp low byte
                self.tL = (self.tL << 1) + val
            elif self.bit >= 16:
                # in temp high byte
                self.tH = (self.tH << 1) + val
            elif self.bit >= 8:
                # in humidity low byte
                self.hL = (self.hL << 1) + val
            elif self.bit >= 0:
                # in humidity high byte
                self.hH = (self.hH << 1) + val
            else:
                # header bits
                pass
            self.bit += 1

        elif level == 1:
            self.high_tick = tick
            if diff > 250000:
                self.bit = -2
                self.hH = 0
                self.hL = 0
                self.tH = 0
                self.tL = 0
                self.CS = 0
        else:
            # level == pigpio.TIMEOUT:
            self.pi.set_watchdog(self.gpio, 0)
            if self.bit < 8:  # Too few data bits received.
                self.bad_MM += 1  # Bump missing message count.
                self.no_response += 1
                if self.no_response > self.MAX_NO_RESPONSE:
                    self.no_response = 0
                    self.bad_SR += 1  # Bump sensor reset count.
                    if self.power is not None:
                        self.powered = False
                        self.pi.write(self.power, 0)
                        time.sleep(2)
                        self.pi.write(self.power, 1)
                        time.sleep(2)
                        self.powered = True

            elif self.bit < 39:
                # Short message receieved.
                self.bad_SM += 1  # Bump short message count.
                self.no_response = 0
            else:
                # Full message received.
                self.no_response = 0

    def temperature(self):
        """Return current temperature."""
        return self.temp

    def humidity(self):
        """Return current relative humidity."""
        return self.rhum

    def staleness(self):
        """Return time since measurement made."""
        if self.tov is not None:
            return time.time() - self.tov
        else:
            return -999

    def bad_checksum(self):
        """Return count of messages received with bad checksums."""
        return self.bad_CS

    def short_message(self):
        """Return count of short messages."""
        return self.bad_SM

    def missing_message(self):
        """Return count of missing messages."""
        return self.bad_MM

    def sensor_resets(self):
        """Return count of power cycles because of sensor hangs."""
        return self.bad_SR

    def trigger(self):
        """Trigger a new relative humidity and temperature reading."""
        if self.powered:
            if self.LED is not None:
                self.pi.write(self.LED, 1)

            self.pi.write(self.gpio, pigpio.LOW)
            time.sleep(0.017)  # 17 ms
            self.pi.set_mode(self.gpio, pigpio.INPUT)
            self.pi.set_watchdog(self.gpio, 200)

    def cancel(self):
        """Cancel the DHT22 sensor."""
        self.pi.set_watchdog(self.gpio, 0)
        if self.cb != None:
            self.cb.cancel()
            self.cb = None

    def temp_c_to_f(self, temp):
        self.temp = temp
        return self.temp * 9 / 5 + 32

    def temp_c_to_k(self, temp):
        self.temp = temp
        return self.temp + 273.15

    def temp_c_to_r(self, temp):
        self.temp = temp
        return self.temp * 9/5 + 491.67

if __name__ == '__main__':

    import DHT22

    is_docker = os.environ.get("IS_DOCKER")

    init = DHT22.Setup()

    if is_docker:
        args = DHT22.Docker()
        logger = init.setup_logger(args.file)
    else:
        args = init.make_args()
        logger = init.setup_logger(args.file)

    pi = pigpio.pi()
    s = DHT22.Sensor(pi, args.gpio, LED=16, power=8)
    INTERVAL = args.interval
    next_reading = time.time()

    while True:
        s.trigger()
        time.sleep(0.2)

        if args.temp == 'C':
            temp = s.temperature()
        elif args.temp == 'F':
            temp = s.temp_c_to_f(s.temperature())
        elif args.temp == 'K':
            temp = s.temp_c_to_k(s.temperature())
        elif args.temp == 'R':
            temp = s.temp_c_to_r(s.temperature())
        humidity = s.humidity()

        init.write_log(logger, args.warn, temp, humidity, args.upper, args.lower, args.pushbullet)

        next_reading += INTERVAL

        # Overall INTERVAL second polling.
        time.sleep(next_reading - time.time())

    s.cancel()

    for handler in logger.handlers:
        handler.close()
        logger.removeFilter(handler)

    pi.stop()
