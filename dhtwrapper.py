#!/usr/bin/env python
# by J. Grant Boling: gboling [at] gmail [dot] com

import subprocess
"""
Wrapper to read data from DHT11 temp/humidity sensor.
"""

def read_dht(DHT_PIN):
    """Read dht output and parse it."""
    _dhtpin = '-g'+str(DHT_PIN)
    dht_read = subprocess.Popen(['DHTXXD', _dhtpin], stdout=subprocess.PIPE,)
    dht_output = dht_read.communicate()
    do = str(dht_output[0])
    dl = do.rstrip()
    dht_list = map(float, dl.split(' '))
#    _dhterr = dht_list[0]
#    _temp = dht_list[1]
#    _hum = dht_list[2]
#    print "Temp: "+str(_temp)+"C"
#    print "Humidity: "+str(_hum)+"%"
#
#if _dhterr != 0: print "DHT11 COMMUNICATIONS ERROR -- CHECK WIRING!"
    return dht_list
