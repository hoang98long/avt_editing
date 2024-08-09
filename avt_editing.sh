#!/bin/bash

# shellcheck disable=SC2164
cd /home/avt/github/avt_editing
conda activate avt_editing
echo $1
python main.py --config_file $1