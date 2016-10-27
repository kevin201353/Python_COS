#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 ShenCloud Inc.

"""log module"""

import os
import logging
import time

from customtimer import CustomTimer

MAX_LOG_SIZE = 10 * 1024 * 1024  # 10M

stdout_bak = os.dup(1)
stderr_bak = os.dup(2)
log_dir = '/var/log/sycos/'

def mkdir(path):
    path = path.strip()
    path = path.rstrip("/")

    is_exists = os.path.exists(path)

    if not is_exists:
        os.makedirs(path)
        return True
    else:
        return False

mkdir(log_dir)

format_ = '%(asctime)s  %(filename)s[line:%(lineno)d] \n\t[%(levelname)s] %(message)s'
(year, month, day, hour, minute, sec, _, _, _) = time.localtime()
file_name = 'sycos_%04d_%02d_%02d_%02d_%02d_%02d.log' \
                % (year, month, day, hour, minute, sec)
log_file_name = os.path.join(log_dir, file_name)
print 'SYCOS', log_file_name
stream = None

def del_old_log():
    log_files = os.listdir(log_dir)
    for file in log_files:
        full_path = os.path.join(log_dir, file)
        if not os.path.isdir(full_path):
            (_, file_year, file_month, file_day, _, _, _) = file.split('_')
            file_year = int(file_year)
            file_month = int(file_month)
            file_day = int(file_day)
            if file_year < year or file_month + 1 < month:
                os.remove(full_path)

def clean_logfile(file_name):
    with open(file_name, 'a') as stream:
        stream.truncate(0)
        stream.flush()

def check_log_size(file_name):
    if os.path.getsize(file_name) > MAX_LOG_SIZE:
        clean_logfile(file_name)

    return True

def init_log(file_level=logging.DEBUG, console_level=logging.ERROR):
    global format_, log_file_name, stream
    del_old_log()
    stream = open(log_file_name, 'a')
    os.dup2(stream.fileno(), 1)
    os.dup2(stream.fileno(), 2)
    stream.close()
    log_check_timer = CustomTimer(60, check_log_size, args=[log_file_name])
    log_check_timer.start()
    logging.basicConfig(level=file_level,
                        format=format_,
                        # filename=log_file_name,
                        filemode='w')

    # console = logging.StreamHandler()
    # console.setLevel(console_level)
    # format_ = '%(filename)s[line:%(lineno)d] [%(levelname)s] %(message)s'
    # formatter = logging.Formatter(format_)
    # console.setFormatter(formatter)
    # logging.getLogger('').addHandler(console)


def destroy_log():
    global stdout_bak, stderr_bak, stream
    os.dup2(stdout_bak, 1)
    os.dup2(stderr_bak, 2)

    global log_file_name
    log_file = open(log_file_name, 'r')
    print log_file.read()
