import ftplib
import os.path
from utils.config import *
from utils.editing_tool import Editing_Tool
import psycopg2
import json
import datetime
import ast

ftp_directory = json.load(open("ftp_directory.json"))
FTP_MERGE_TIFF_PATH = ftp_directory['merge_tiffs_result_directory']


def connect_ftp(config_data):
    ftp = ftplib.FTP()
    ftp.connect(config_data['ftp']['host'], config_data['ftp']['port'])
    ftp.set_pasv(True)
    ftp.login(user=config_data['ftp']['user'], passwd=config_data['ftp']['password'])
    return ftp


def check_and_create_directory(ftp, directory):
    try:
        ftp.cwd(directory)
    except ftplib.error_perm as e:
        if str(e).startswith('550'):
            ftp.mkd(directory)
        else:
            print(f"Error changing to directory '{directory}': {e}")


def download_file(ftp, ftp_file_path, local_file_path):
    try:
        with open(local_file_path, 'wb') as file:
            ftp.retrbinary(f"RETR {ftp_file_path}", file.write)
        print(f"Downloaded '{ftp_file_path}' to '{local_file_path}'")
    except ftplib.all_errors as e:
        print(f"FTP error: {e}")


def route_to_db(cursor):
    cursor.execute('SET search_path TO public')
    cursor.execute("SELECT current_schema()")


class Editing:
    def __init__(self):
        pass

    def merge_tiffs(self, conn, id, task_param, config_data):
        input_files = task_param['input_files']
        input_files = ast.literal_eval(input_files)
        try:
            ftp = connect_ftp(config_data)
            input_files_local = []
            for input_file in input_files:
                filename = input_file.split("/")[-1]
                local_file_path = os.path.join(LOCAL_SRC_MERGE_TIFF_PATH, filename)
                input_files_local.append(local_file_path)
                download_file(ftp, input_file, local_file_path)
            date_create = str(datetime.datetime.now().date()).replace('-', '_')
            output_image_name = "result_merge" + "_" + format(date_create) + ".tiff"
            output_path = os.path.join(LOCAL_RESULT_MERGE_TIFF_PATH, output_image_name)
            editing_tool = Editing_Tool()
            editing_tool.merge_tiffs(input_files_local, output_path)
            ftp_dir = FTP_MERGE_TIFF_PATH
            ftp.cwd(str(ftp_dir))
            save_dir = ftp_dir + "/" + output_image_name
            task_output = str({
                "output_image": save_dir
            })
            with open(output_path, "rb") as file:
                ftp.storbinary(f"STOR {save_dir}", file)
            print("Connection closed")
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 1, task_output = %s WHERE id = %s", (task_output, id,))
            conn.commit()
        except ftplib.all_errors as e:
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 0 WHERE id = %s", (id,))
            conn.commit()
            print(f"FTP error: {e}")

    def crop_tiff_image(self, conn, id, task_param, config_data):
        input_file = task_param['input_file']
        xmin = float(task_param['xmin'])
        xmax = float(task_param['xmax'])
        ymin = float(task_param['ymin'])
        ymax = float(task_param['ymax'])
        try:
            ftp = connect_ftp(config_data)
            filename = input_file.split("/")[-1]
            local_file_path = os.path.join(LOCAL_SRC_MERGE_TIFF_PATH, filename)
            download_file(ftp, input_file, local_file_path)
            date_create = str(datetime.datetime.now().date()).replace('-', '_')
            output_image_name = "result_crop" + "_" + format(date_create) + ".tiff"
            output_path = os.path.join(LOCAL_RESULT_MERGE_TIFF_PATH, output_image_name)
            editing_tool = Editing_Tool()
            editing_tool.crop_tiff_image(local_file_path, output_path, xmin, ymin, xmax, ymax)
            ftp_dir = FTP_MERGE_TIFF_PATH
            ftp.cwd(str(ftp_dir))
            save_dir = ftp_dir + "/" + output_image_name
            task_output = str({
                "output_image": save_dir
            })
            with open(output_path, "rb") as file:
                ftp.storbinary(f"STOR {save_dir}", file)
            print("Connection closed")
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 1, task_output = %s WHERE id = %s", (task_output, id,))
            conn.commit()
        except ftplib.all_errors as e:
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 0 WHERE id = %s", (id,))
            conn.commit()
            print(f"FTP error: {e}")


    def process(self, id, config_data):
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
        cursor.execute("SELECT task_param FROM avt_task WHERE id = %s", (id,))
        result = cursor.fetchone()
        task_param = json.loads(result[0])
        algorithm = task_param["algorithm"]
        if algorithm == "ghep_anh":
            self.merge_tiffs(conn, id, task_param, config_data)
        elif algorithm == "cat_anh":
            self.crop_tiff_image(conn, id, task_param, config_data)
        cursor.close()
