#!/usr/bin/env python

# PIR control of the rpi camera with DHT sensor, automatically sorting new video into directories by date.
# by J. Grant Boling: gboling [at] gmail [dot] com
# with guidance from http://nestboxtech.blogspot.co.uk/2014/11/how-to-make-your-own-raspberry-pi-trail.html
# Remember to make sure pigpiod service is running if you intend to log from the DHT11!

import time
import datetime
import sys
import os
import subprocess
from collections import namedtuple

import picamera
import RPi.GPIO as GPIO

import dhtwrapper
import datedir
import diskusage

# Set up GPIO, change PIR_PIN, DHT_PIN if you plan to plug your sensors into different GPIO pins.
GPIO.setmode(GPIO.BCM)
PIR_PIN = 17
# Set ENABLE_DHT to True if you're planning to log from a DHT11.
ENABLE_DHT = False
DHT_PIN = 18
GPIO.setup(PIR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
dhtpin = '-g'+str(DHT_PIN)

# Camera settings
FRAME_RATE = 24
CAM_RESOLUTION = (1280, 720)
REC_TIME = 15


# Where will we store our files? Set a limit (percentage of diskspace free) so we don't fill up the disk.
RAW_FILE_HEAD = "/home/pi/Videos/owlCamProject"
FREE_SPACE_LIMIT = 10
# RAW_FILE_TAIL sets the output filename, the timestamp will be appended to this.
RAW_FILE_TAIL = "owlCam_"
basedir = os.path.join(RAW_FILE_HEAD, "owlCamVid")

# Classes:
class DiskFreeThreshold(Exception):
    def __init__( self, day_dir ):
        free_pct = diskFree(day_dir)
        Exception.__init__(self, 'Free Diskspace Threshold Reached exception: %s%% free' % str(free_pct))

def buildDayDir():
    """Make year/month/day directory and export a variable of the day's directory"""
    global day_dir
    day_dir = datedir.datedir(basedir)
    return day_dir

def tempHumidity():
    """Query the DHT11 Temp/Humidity sensor and set variables."""
    global dht_list
    dht_list = dhtwrapper.read_dht(DHT_PIN)
    return dht_list

def diskFree(day_dir):
    """Get disk usage percentage and turn it into percent free."""
    u_pct = getattr(diskusage.disk_usage(day_dir), 'percent')
    global free_pct
    free_pct = 100 - u_pct
    return free_pct

def recordImage2(day_dir):
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
    h264_save_file_join = os.path.join(RAW_FILE_HEAD, h264_save_file_tail)
    (save_file_short, save_file_ext) = os.path.splitext(h264_save_file_tail)
    mp4_save_file_tail = os.path.join(save_file_short+'.mp4')
    mp4_save_file_join = os.path.join(day_dir, mp4_save_file_tail)
    with picamera.PiCamera() as camera:
        camera.led = False
        camera.vflip = True
        camera.hflip = True
        camera.exposure_mode = ('night')
        camera.framerate = FRAME_RATE
#        camera.start_preview()
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
        subprocess.call(['avconv', '-r', str(FRAME_RATE), '-i', h264_save_file_join, '-vcodec', 'copy', mp4_save_file_join])
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
        buildDayDir()
        global free_pct
        free_pct = diskFree(day_dir)
        print "%s%% free on disk" % str(free_pct)
#        if free_pct < FREE_SPACE_LIMIT: raise DiskFreeThreshold(day_dir)
        recordImage2(day_dir)
        return free_pct

day_dir = datedir.datedir(basedir)
free_pct = diskFree(day_dir)
print "PIR Camera Control Test (CTRL+C to exit)"
time.sleep(5)
print "Ready"

try:
    GPIO.add_event_detect(PIR_PIN, GPIO.RISING, callback=MOTION)
    while free_pct > FREE_SPACE_LIMIT:
        time.sleep(100)
    else:
        raise DiskFreeThreshold(day_dir)

except DiskFreeThreshold, exc:
    print exc
    sys.exit(1)

except KeyboardInterrupt:
    print " Quit"

finally:
    GPIO.cleanup()
