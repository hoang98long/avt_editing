import argparse
from utils.editing import Editing
import json


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--avt_task_id', type=int, required=True, help='task id')
    parser.add_argument('--config_file', type=str, required=True, help='config file')
    args = parser.parse_args()
    editing = Editing()
    config_data = json.load(open(args.config_file))
    editing.process(args.avt_task_id, config_data)
