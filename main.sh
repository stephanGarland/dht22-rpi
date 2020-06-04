#!/bin/bash
set -m
pigpiod
python DHT22.py -i 3
