# Raspberry-Bushcam
by J. Grant Boling: gboling [at] gmail [dot] com

A python script which uses the Raspberry Pi to record video of wildlife when triggered by PIR sensor. 
Optionally supports DHT11/22/AM2302 temp/humidity sensor.
Handles encoding the raw h264 files to mp4 and copies to a folder organized as such: year/month/date.
Video files are annotated with timestamp and temp/humidity at time of trigger. Filename is also the timestamp.

Dependencies:
------------

Raspberry Pi 2 B with Camera, picamera-dev
PIR sensor,
Raspbian Jessie,
pigpiod http://abyz.co.uk/rpi/pigpio/pigpiod.html
https://github.com/adafruit/Adafruit_Python_DHT

Default GPIO inputs:
PIR : GPIO pin 17
DHT : GPIO pin 18

See raspberry-bushcam.conf for configuration.
