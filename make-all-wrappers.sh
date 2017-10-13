#!/bin/sh
mkdir -p bin
./make_wrappers.py i386-linux-gnu
./make_wrappers.py x86_64-linux-gnux32
