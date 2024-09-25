import argparse
import time
from utils.editing import Editing
import json
import psycopg2
import os
import schedule


def get_task_id_list(task_type):
    conn = psycopg2.connect(
        dbname=config_data['database']['database'],
        user=config_data['database']['user'],
        password=config_data['database']['password'],
        host=config_data['database']['host'],
        port=config_data['database']['port']
    )
    cursor = conn.cursor()
    cursor.execute('SET search_path TO public')
    cursor.execute("SELECT current_schema()")
    cursor.execute("SELECT id FROM avt_task WHERE task_type = %s and task_stat < 0 ORDER BY task_stat DESC",
                   (task_type,))
    result = cursor.fetchall()
    return [res[0] for res in result]


def delete_files_with_prefix(directory, prefix='result_'):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.startswith(prefix):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                except Exception as e:
                    pass


def daily_cleanup():
    directory = 'images/'
    delete_files_with_prefix(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # parser.add_argument('--avt_task_id', type=int, required=True, help='task id')
    parser.add_argument('--config_file', type=str, required=True, help='config file')
    args = parser.parse_args()
    schedule.every(1).days.do(daily_cleanup)
    while True:
        config_data = json.load(open(args.config_file))
        task_type = 9
        list_task = get_task_id_list(task_type)
        if len(list_task) > 0:
            for task_id in list_task:
                editing = Editing()
                editing.process(task_id, config_data)
        schedule.run_pending()
        time.sleep(5)
