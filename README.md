# Rpi-WLcam
By: J. Grant Boling

A python script for the Raspberry Pi to record video of wildlife when triggered by PIR sensor. Also supports DHT11 temp/humidity sensor. Handles encoding the raw h264 files to mp4 and copies to a folder organized as such: year/month/date. Video files are annotated with timestamp and temp/humidity at time of trigger. Filename is also the timestamp.

Dependencies:

Raspberry Pi 2 B with Camera,
PIR sensor,
Raspbian Jessie,
pigpiod http://abyz.co.uk/rpi/pigpio/pigpiod.html
DHTXXD  http://abyz.co.uk/rpi/pigpio/examples.html
