#!/bin/bash
wget https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz -O /tmp/ffmpeg.tar.xz
tar xf /tmp/ffmpeg.tar.xz -C /tmp --strip-components=1
cp /tmp/ffmpeg /usr/local/bin/
