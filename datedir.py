#!/usr/bin/env python

# To make a directory for each calendar day.

import time
import datetime
import os


def datedir(basedir):
    """Check if the directory tree exists and build it if not."""

    today = datetime.date.today()
    t_year = today.strftime('%Y')
    t_month = today.strftime('%m')
    t_day = today.strftime('%d')
    year_dir = os.path.join(basedir, t_year)
    month_dir = os.path.join(year_dir, t_month)
    day_dir = os.path.join(month_dir, t_day)

    if not os.path.exists(basedir):
        os.makedirs(basedir)

    if not os.path.exists(year_dir):
        os.mkdir(year_dir)

    if not os.path.exists(month_dir):
        os.mkdir(month_dir)

    if not os.path.exists(day_dir):
        os.mkdir(day_dir)

    return day_dir
