#!/usr/bin/env python

"""
PIR control of the Raspberry Pi camera with DHT sensor, automatically sorting new video into directories by date.
Optionally writes to mysql database at user-defined interval.
by J. Grant Boling: gboling [at] gmail [dot] com
with guidance from http://nestboxtech.blogspot.co.uk/2014/11/how-to-make-your-own-raspberry-pi-trail.html
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

import Adafruit_DHT
import MySQLdb
import timedir
import diskusage
import schedule
import threading

config = {}
execfile("raspberry-bushcam.conf", config)
if config["bcm_mode"]:
    GPIO.setmode(GPIO.BCM)
else:
    GPIO.setmode(GPIO.BOARD)
PIR_PIN = config["pir_pin"]
DHT_TYPE = config["dht_type"]
DHT_PIN = config["dht_pin"]
cam_led_enable = config["cam_led_enable"]
GPIO.setup(PIR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(DHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Camera settings
FRAME_RATE = config["frame_rate"]
CAM_RESOLUTION = config["resolution"]
REC_TIME = config["rec_time"]

# SQL settings
mysql_enable = config["mysql_enable"]
mysql_host = config["mysql_host"]
mysql_user = config["mysql_user"]
mysql_pw = config["mysql_pw"]
mysql_db = config["mysql_db"]
conn = MySQLdb.connect(host= mysql_host, user= mysql_user, passwd=mysql_pw, db=mysql_db)
mysql_cursor=conn.cursor()

# Deal with command-line arguments
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
wlc_parser.add_argument('-t', '--enable-temp',
                    dest="ENABLE_DHT",
                    default=False,
                    action='store_true',
                    help="Enable temperature and humidity logging from DHT11."
                    )
wlc_parser.add_argument('-f', '--sampling-frequency',
                    dest="sampFreq",
                    default="60",
                    help="Record temperature and humidity every x seconds.",
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
sampFreq = int(wlc_args.sampFreq)
now = datetime.datetime.now()
timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
if ENABLE_DHT: (humidity, temp) = Adafruit_DHT.read_retry(DHT_TYPE, DHT_PIN)

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

def MOTION(PIR_PIN):
    if GPIO.event_detected(PIR_PIN):
        ts = getTimestamp()
        print "Motion detected at: "+ts
        buildOutputDir()
        global free_pct
        global mp4_save_file_join
        free_pct = diskFree(working_dir)
        print "%s%% free on disk" % str(free_pct)
#        run_threaded(recordImage2(working_dir))
        recordImage2(working_dir)
        return free_pct

def buildOutputDir():
    """Make year/month/day directory and export a variable of the day's directory"""
    global working_dir
    timedir.nowdir(output_dir, scopelevel)
    working_dir = getattr(timedir.nowdir(output_dir, scopelevel), scopedir)
    return working_dir

def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    job_thread.start()

def tempHumidity():
    """Query the DHT11 Temp/Humidity sensor and set variables."""
    global temp, humidity
    (humidity, temp) = Adafruit_DHT.read_retry(DHT_TYPE, DHT_PIN)
    print "Temp: "+str(temp)+"C"
    print "Humidity: "+str(humidity)+"%"
    return (temp, humidity)

def writesql(timestamp, temp, humidity, *mp4_save_file_join):
    """Record temp humidity and time to sql database."""
    if mp4_save_file_join:
        (filename,) = mp4_save_file_join
        print filename
        fn_insert = 'INSERT INTO readings (Timestamp, Temperature, Humidity, video_filename) VALUES (\'{0}\', \'{1}\', \'{2}\', \'{3}\')'
        fn_ondupe = ' ON DUPLICATE KEY UPDATE video_filename = \'{0}\';'.format(filename)
        fn_query = fn_insert.format(timestamp, temp, humidity, filename)+fn_ondupe
        print "SQL COMMAND: "+fn_query
#        print "SQL COMMAND: "+fn_ondupe
        mysql_cursor.execute(fn_query)
#        c.execute(fn_ondupe)
#        c.execute("INSERT INTO readings (Timestamp, Temperature, Humidity, video_filename) VALUES (%s, %s, %s, %s)",(timestamp, temp, humidity, mp4_save_file_join))
    else:
        if ENABLE_DHT:         mysql_cursor.execute("INSERT INTO readings (Timestamp, Temperature, Humidity) VALUES (%s, %s, %s)",(timestamp, temp, humidity))
    conn.commit()
    print "Sensor data recorded to mysql database: "+mysql_db+" at "+timestamp
    return

def getTimestamp():
    """Find out what time it is and apply it to the timestamp variable."""
    global timestamp
    now = datetime.datetime.now()
    timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
    return timestamp

def sampleRecord():
    """Get a timestamp, data from sensor, and record it to a database or file."""
    ts = getTimestamp()
    (temp_samp, hum_samp) = tempHumidity()
    writesql(ts, temp_samp, hum_samp)
    return

def diskFree(working_dir):
    """Get disk usage percentage and turn it into percent free."""
    u_pct = getattr(diskusage.disk_usage(working_dir), 'percent')
    global free_pct
    free_pct = 100 - u_pct
    return free_pct

def recordImage2(working_dir):
    """Records video from the rpi camera, encodes it to mp4 and copies it to a
    directory for that calendar date."""
    if ENABLE_DHT:
        temp_c, hum_pct = tempHumidity()
    h264_save_file_tail = RAW_FILE_TAIL+timestamp+'.h264'
    h264_save_file_join = os.path.join(FILE_HEAD_ARG, h264_save_file_tail)
    (save_file_short, save_file_ext) = os.path.splitext(h264_save_file_tail)
    mp4_save_file_tail = os.path.join(save_file_short+'.mp4')
    mp4_save_file_join = os.path.join(working_dir, mp4_save_file_tail)
    with picamera.PiCamera() as camera:
        camera.led = cam_led_enable
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
        if mysql_enable: writesql(timestamp, temp, humidity, mp4_save_file_join)
    return mp4_save_file_join

#logging.basicConfig(filename=RAW_FILE_HEAD. loglevel=logging.DEBUG)
working_dir = getattr(timedir.nowdir(output_dir, scopelevel), scopedir)
free_pct = diskFree(working_dir)
if sampFreq and not ENABLE_DHT: print "WARNING: Unable to set sample frequency as the DHT sensor is not enabled."
if ENABLE_DHT and sampFreq: schedule.every(sampFreq).seconds.do(run_threaded, sampleRecord)
print "PIR Camera Control Test (CTRL+C to exit)"
time.sleep(5)
print "Ready"
print "Started at "+timestamp

try:
    GPIO.add_event_detect(PIR_PIN, GPIO.RISING, callback=MOTION)
    while free_pct > FREE_SPACE_LIMIT:
        schedule.run_pending()
        time.sleep(1)
    else:
        raise DiskFreeThreshold(working_dir)

except DiskFreeThreshold, exc:
    print exc
    sys.exit(1)

except KeyboardInterrupt:
    print " Quit"

finally:
    GPIO.cleanup()
    if mysql_enable:
        mysql_cursor.close
        conn.close()
