#!/bin/bash

CONFIG_FILE=$1

cd /home/avt/github/avt_editing
conda activate avt_editing
python main.py "$CONFIG_FILE"
