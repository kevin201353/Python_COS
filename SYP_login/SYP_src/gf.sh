#!/bin/bash
#
# gf Cloud Desktop Entry Point
#
#

ROOTDIR=/usr/share/gclient
LAUNCHER=gf_launch.sh
sed -i '/rm -rf .pulse/d' ~/.bash_profile
sed -i '/cd ~/d' ~/.bash_profile
sed -i '$a\cd ~' ~/.bash_profile
sed -i '$a\rm -rf .pulse' ~/.bash_profile
cp -f  /usr/share/gclient/pcmanfm.conf ~/.config/pcmanfm/LXDE/
cp -f  /usr/share/gclient/lxde-rc.xml ~/.config/openbox/
cp -f $ROOTDIR/$LAUNCHER /tmp
bash -x /tmp/$LAUNCHER

