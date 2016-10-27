#!/bin/bash
#
# gf Cloud Desktop Entry Point
#
#

# Backup log files
LOG_DIR=~/logbackup
EXT=`date +%Y%m%d`
FILENAME=zvmclient.log
LOGFILENAME=~/$FILENAME
BACKUP_FILENAME=$LOG_DIR/$FILENAME.$EXT

mkdir -vp $LOG_DIR

if [ ! -f $BACKUP_FILENAME.gz ]; then
	mv $LOGFILENAME $BACKUP_FILENAME
	gzip $BACKUP_FILENAME
fi

# Disable Power Saving
pm-powersave false

# Update Client
# Disable auto update for security reason
#python /usr/share/gclient/Update.pyc >> $FILENAME
sed -i '/rm -rf .pulse/d' ~/.bash_profile
sed -i '/cd ~/d' ~/.bash_profile
sed -i '$a\cd ~' ~/.bash_profile
sed -i '$a\rm -rf .pulse' ~/.bash_profile
cp -f  /usr/share/gclient/pcmanfm.conf ~/.config/pcmanfm/LXDE/
cp -f  /usr/share/gclient/lxde-rc.xml ~/.config/openbox/
cd /usr/share/gclient
python Main.pyc
