#!/usr/bin/env python

"""
PIR control of the rpi camera with DHT sensor, automatically sorting new video into directories by date.
by J. Grant Boling: gboling [at] gmail [dot] com
with guidance from http://nestboxtech.blogspot.co.uk/2014/11/how-to-make-your-own-raspberry-pi-trail.html
Remember to make sure pigpiod service is running if you intend to log from the DHT11!
"""

import time
import datetime
import sys
import os
import subprocess
import logging
import argparse
from collections import namedtuple

import picamera
import RPi.GPIO as GPIO

import dhtwrapper
import timedir
import diskusage

# Set up GPIO, change PIR_PIN, DHT_PIN if you plan to plug your sensors into different GPIO pins.
GPIO.setmode(GPIO.BCM)
config = {}
execfile("rpi-wlcam.conf", config)
PIR_PIN = config["pir_pin"]
# Set ENABLE_DHT to True if you're planning to log from a DHT11.
DHT_PIN = config["dht_pin"]
GPIO.setup(PIR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(DHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
dhtpin = '-g'+str(DHT_PIN)

# Camera settings
FRAME_RATE = config["frame_rate"]
CAM_RESOLUTION = config["resolution"]
REC_TIME = config["rec_time"]

wlc_parser = argparse.ArgumentParser(description='Record video on a Raspberry Pi 2 triggered by PIR sensor. Also records temp/humidity from DHT11.')
wlc_parser.add_argument('FILE_HEAD_ARG',
                    default=os.getcwd(),
                    help="Specify the output directory, will be created if it does not exist."
                    )
wlc_parser.add_argument('-v', '--verbose',
                    dest="verbose",
                    default=False,
                    action='store_true',
                    help="Not implemented yet."
                    )
wlc_parser.add_argument('-s', '--scope',
                    dest="scope",
                    choices=["year", "month", "day", "hour", "min"],
                    default="day",
                    help="Specify how deep to make the directory tree."
                    )
wlc_parser.add_argument('-T', '--enable-temp',
                    dest="ENABLE_DHT",
                    default=False,
                    action='store_true',
                    help="Enable temperature and humidity logging from DHT11."
                    )

wlc_args = wlc_parser.parse_args()

# Directory for raw video files and logs.
FILE_HEAD_ARG = wlc_args.FILE_HEAD_ARG
#  Set a limit (percentage of diskspace free) so we don't fill up the disk.
FREE_SPACE_LIMIT = config["diskspace_limit"]
# RAW_FILE_TAIL sets the output filename, the timestamp will be appended to this.
RAW_FILE_TAIL = config["h264filename_base"]
# Directory for video output, organized by year/month/day.
MP4_FILE_HEAD = config["mp4filename_base"]
output_dir = os.path.join(FILE_HEAD_ARG, MP4_FILE_HEAD)
ENABLE_DHT = wlc_args.ENABLE_DHT

if wlc_args.scope == "year": scopelevel = 0; scopedir = "yearDir"

if wlc_args.scope == "month": scopelevel = 1; scopedir = "monthDir"

if wlc_args.scope == "day": scopelevel = 2; scopedir = "dayDir"

if wlc_args.scope == "hour": scopelevel = 3; scopedir = "hourDir"

if wlc_args.scope == "min": scopelevel = 4; scopedir = "minDir"

# Classes:
class DiskFreeThreshold(Exception):
    def __init__( self, working_dir ):
        free_pct = diskFree(working_dir)
        Exception.__init__(self, 'Free Diskspace Threshold Reached exception: %s%% free' % str(free_pct))

def buildOutputDir():
    """Make year/month/day directory and export a variable of the day's directory"""
    global working_dir
    timedir.nowdir(output_dir, scopelevel)
    working_dir = getattr(timedir.nowdir(output_dir, scopelevel), scopedir)
    return working_dir

def tempHumidity():
    """Query the DHT11 Temp/Humidity sensor and set variables."""
    global dht_list
    dht_list = dhtwrapper.read_dht(DHT_PIN)
    return dht_list

def diskFree(working_dir):
    """Get disk usage percentage and turn it into percent free."""
    u_pct = getattr(diskusage.disk_usage(working_dir), 'percent')
    global free_pct
    free_pct = 100 - u_pct
    return free_pct

def recordImage2(working_dir):
    """Records video from the rpi camera, encodes it to mp4 and copies it to a
    directory for that calendar date."""

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
    print "Motion detected: "
    print str(timestamp)
    if ENABLE_DHT:
        dht_err, temp_c, hum_pct = tempHumidity()
        if dht_err != 0: print "DHT COMMUNICATIONS ERROR -- CHECK WIRING!"
        else:
            print "Temp: "+str(temp_c)+"C"
            print "Humidity: "+str(hum_pct)+"%"
    h264_save_file_tail = RAW_FILE_TAIL+timestamp+'.h264'
    h264_save_file_join = os.path.join(FILE_HEAD_ARG, h264_save_file_tail)
    (save_file_short, save_file_ext) = os.path.splitext(h264_save_file_tail)
    mp4_save_file_tail = os.path.join(save_file_short+'.mp4')
    mp4_save_file_join = os.path.join(working_dir, mp4_save_file_tail)
    with picamera.PiCamera() as camera:
        camera.led = False
        camera.vflip = True
        camera.hflip = True
        camera.exposure_mode = ('night')
        camera.framerate = FRAME_RATE
        camera.start_preview()
        time.sleep(2)
        camera.annotate_background = picamera.Color('black')
        if ENABLE_DHT:
            camera.annotate_text = now.strftime('%Y-%m-%d %H:%M:%S')+' Temp: '+str(temp_c)+'C '+'Humidity: '+str(hum_pct)+'%'
        else:
            camera.annotate_text = now.strftime('%Y-%m-%d %H:%M:%S')
        camera.resolution = CAM_RESOLUTION
#        camera.capture_sequence(['/home/pi/owlCam/owlCam_'+timestamp+'_image%02d.jpg' % i for i in range(3)])
#        camera.start_recording('/home/pi/owlCam/pix/owlCam_'+timestamp+'.h264')
        camera.start_recording(h264_save_file_join)
        camera.wait_recording(REC_TIME)
        camera.stop_recording()
        print "Video recorded to "+h264_save_file_join
        camera.close()
        time.sleep(1)
# Encode the video file so we can watch it. This is an inefficient way to do this, should learn how to encode from a stream.
        subprocess.call(['avconv', '-i', h264_save_file_join, '-r', str(FRAME_RATE), '-vcodec', 'copy', mp4_save_file_join])
        print "Video encoded to "+mp4_save_file_join
        time.sleep(2)
        if os.path.isfile(mp4_save_file_join):
            print "Cleaning up..."
            os.remove(h264_save_file_join)
            print "Done cleaning up."
        else:
            print "Transcoding FAILED, "+h264_save_file_join+" must be re-encoded before it will play."

def MOTION(PIR_PIN):
    if GPIO.event_detected(PIR_PIN):
        buildOutputDir()
        global free_pct
        free_pct = diskFree(working_dir)
        print "%s%% free on disk" % str(free_pct)
        recordImage2(working_dir)
        return free_pct

#logging.basicConfig(filename=RAW_FILE_HEAD. loglevel=logging.DEBUG)
working_dir = getattr(timedir.nowdir(output_dir, scopelevel), scopedir)
free_pct = diskFree(working_dir)
print "PIR Camera Control Test (CTRL+C to exit)"
time.sleep(5)
print "Ready"

try:
    GPIO.add_event_detect(PIR_PIN, GPIO.RISING, callback=MOTION)
    while free_pct > FREE_SPACE_LIMIT:
        time.sleep(100)
    else:
        raise DiskFreeThreshold(working_dir)

except DiskFreeThreshold, exc:
    print exc
    sys.exit(1)

except KeyboardInterrupt:
    print " Quit"

finally:
    GPIO.cleanup()
