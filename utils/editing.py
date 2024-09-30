import ftplib
import os.path
from utils.config import *
from utils.editing_tool import Editing_Tool
import psycopg2
import json
from datetime import datetime
import time
import threading
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import ast


ftp_directory = json.load(open("ftp_directory.json"))
FTP_MERGE_TIFF_PATH = ftp_directory['merge_tiffs_result_directory']
FTP_CROP_TIFF_PATH = ftp_directory['crop_tiff_result_directory']
FTP_CROP_POLYGON_TIFF_PATH = ftp_directory['crop_tiff_polygon_result_directory']
FTP_STACK_TIFF_PATH = ftp_directory['stack_tiffs_result_directory']


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


def update_database(id, task_stat_value, conn):
    cursor = conn.cursor()
    # Update the task_stat field
    cursor.execute('UPDATE avt_task SET task_stat = %s WHERE id = %s', (task_stat_value, id))
    conn.commit()
    # Select and print the updated row
    # cursor.execute('SELECT * FROM avt_task WHERE id = %s', (id,))
    # row = cursor.fetchone()
    # print(row)


def check_and_update(id, task_stat_value_holder, conn, stop_event):
    start_time = time.time()
    while not stop_event.is_set():
        time.sleep(5)
        if stop_event.is_set():
            break
        elapsed_time = time.time() - start_time
        task_stat_value_holder['value'] = max(2, int(elapsed_time))
        update_database(id, task_stat_value_holder['value'], conn)


def get_time():
    now = datetime.now()
    current_datetime = datetime(now.year, now.month, now.day, now.hour, now.minute, now.second, now.microsecond)
    return current_datetime


def get_time_string():
    now = datetime.now()
    current_datetime = (str(now.year) + "_" + str(now.month) + "_" + str(now.day) + "_"
                        + str(now.hour) + "_" + str(now.minute) + "_" + str(now.second))
    return current_datetime


def check_epsg_code(tiff_path):
    with rasterio.open(tiff_path) as src:
        crs = src.crs
        if crs:
            epsg_code = int(crs.to_epsg())
            return epsg_code
        else:
            return 0


def convert_epsg_4326(input_tiff_path, output_tiff_path, dst_crs='EPSG:4326'):
    with rasterio.open(input_tiff_path) as src:
        src_profile = src.profile

        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds)

        dst_profile = src_profile.copy()
        dst_profile.update({
            'crs': dst_crs,
            'transform': transform,
            'width': width,
            'height': height
        })
        with rasterio.open(output_tiff_path, 'w', **dst_profile) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest)


class Editing:
    def __init__(self):
        pass

    def merge_tiffs(self, conn, id, task_param, config_data):
        input_files = task_param['input_files']
        # print(input_files)
        if len(input_files) < 2:
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute(
                "UPDATE avt_task SET task_stat = 0, task_message = 'Thiếu ảnh để ghép',"
                "updated_at = %s WHERE id = %s", (get_time(), id))
            conn.commit()
            return False
        try:
            ftp = connect_ftp(config_data)
            input_files_local = []
            for input_file in input_files:
                filename = input_file.split("/")[-1]
                local_file_path = os.path.join(LOCAL_SRC_MERGE_TIFF_PATH, filename)
                input_files_local.append(local_file_path)
                if not os.path.isfile(local_file_path):
                    download_file(ftp, input_file, local_file_path)
            for i in range(len(input_files_local)):
                epsg_code = check_epsg_code(input_files_local[i])
                if epsg_code == 0:
                    cursor = conn.cursor()
                    route_to_db(cursor)
                    cursor.execute(
                        "UPDATE avt_task SET task_stat = 0, task_message = 'Không đúng định dạng ảnh tiff EPSG',"
                        "updated_at = %s WHERE id = %s", (get_time(), id))
                    conn.commit()
                    return False
                elif epsg_code != 4326:
                    converted_input_file_local = input_files_local[i].split(".")[0] + "_4326.tif"
                    convert_epsg_4326(input_files_local[i], converted_input_file_local)
                    input_files_local[i] = converted_input_file_local
            date_create = get_time_string()
            output_image_name = "result_merge_" + format(date_create) + ".tif"
            output_path = os.path.join(LOCAL_RESULT_MERGE_TIFF_PATH, output_image_name)
            editing_tool = Editing_Tool()
            intersections = editing_tool.merge_tiffs(input_files_local, output_path)
            ftp_dir = FTP_MERGE_TIFF_PATH
            ftp.cwd(str(ftp_dir))
            save_dir = ftp_dir + "/" + output_image_name
            task_output = str({
                # "output_image": [save_dir]
                "output_image": [save_dir],
                "intersections": str(intersections)
            }).replace("'", "\"")
            with open(output_path, "rb") as file:
                ftp.storbinary(f"STOR {save_dir}", file)
            ftp.sendcmd(f'SITE CHMOD 775 {save_dir}')
            # owner_group = 'avtadmin:avtadmin'
            # chown_command = f'SITE CHOWN {owner_group} {save_dir}'
            # ftp.sendcmd(chown_command)
            # print("Connection closed")
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 1, task_output = %s, updated_at = %s WHERE id = %s",
                           (task_output, get_time(), id,))
            conn.commit()
            return True
        except ftplib.all_errors as e:
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 0, task_message = 'Lỗi đầu vào' WHERE id = %s", (id,))
            conn.commit()
            # print(f"FTP error: {e}")
            return False

    def crop_tiff_image(self, conn, id, task_param, config_data):
        input_file_arr = task_param['input_file']
        if len(input_file_arr) < 1:
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute(
                "UPDATE avt_task SET task_stat = 0, task_message = 'Không có ảnh',"
                "updated_at = %s WHERE id = %s", (get_time(), id))
            conn.commit()
            return False
        input_file = input_file_arr[0]
        rectangle_crop = task_param['polygon']
        rectangle_crop = ast.literal_eval(rectangle_crop)[0]
        try:
            ftp = connect_ftp(config_data)
            filename = input_file.split("/")[-1]
            local_file_path = os.path.join(LOCAL_SRC_CROP_TIFF_PATH, filename)
            if not os.path.isfile(local_file_path):
                download_file(ftp, input_file, local_file_path)
            epsg_code = check_epsg_code(local_file_path)
            if epsg_code == 0:
                cursor = conn.cursor()
                route_to_db(cursor)
                cursor.execute("UPDATE avt_task SET task_stat = 0, task_message = 'Không đúng định dạng ảnh tiff EPSG',"
                               "updated_at = %s WHERE id = %s", (get_time(), id))
                conn.commit()
                return False
            elif epsg_code != 4326:
                converted_input_files_local = local_file_path.split(".")[0] + "_4326.tif"
                convert_epsg_4326(local_file_path, converted_input_files_local)
                local_file_path = converted_input_files_local
            date_create = get_time_string()
            output_image_name = "result_crop_" + format(date_create) + ".tif"
            output_path = os.path.join(LOCAL_RESULT_CROP_TIFF_PATH, output_image_name)
            editing_tool = Editing_Tool()
            editing_tool.crop_polygon_tiff(local_file_path, output_path, rectangle_crop)
            ftp_dir = FTP_CROP_TIFF_PATH
            ftp.cwd(str(ftp_dir))
            save_dir = ftp_dir + "/" + output_image_name
            task_output = str({
                "output_image": [save_dir]
            }).replace("'", "\"")
            with open(output_path, "rb") as file:
                ftp.storbinary(f"STOR {save_dir}", file)
            ftp.sendcmd(f'SITE CHMOD 775 {save_dir}')
            # owner_group = 'avtadmin:avtadmin'
            # chown_command = f'SITE CHOWN {owner_group} {save_dir}'
            # ftp.sendcmd(chown_command)
            # print("Connection closed")
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 1, task_output = %s, updated_at = %s WHERE id = %s",
                           (task_output, get_time(), id,))
            conn.commit()
            return True
        except ftplib.all_errors as e:
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 0, task_message = 'Lỗi đầu vào' WHERE id = %s", (id,))
            conn.commit()
            # print(f"FTP error: {e}")
            return False

    def crop_polygon_tiff(self, conn, id, task_param, config_data):
        input_file_arr = task_param['input_file']
        if len(input_file_arr) < 1:
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute(
                "UPDATE avt_task SET task_stat = 0, task_message = 'Không có ảnh',"
                "updated_at = %s WHERE id = %s", (get_time(), id))
            conn.commit()
            return False
        input_file = input_file_arr[0]
        polygon = task_param['polygon']
        polygon = ast.literal_eval(polygon)[0]
        # print(polygon)
        # polygon = np.array(polygon)
        # polygon = polygon.astype(float)[0]
        try:
            ftp = connect_ftp(config_data)
            filename = input_file.split("/")[-1]
            local_file_path = os.path.join(LOCAL_SRC_CROP_POLYGON_TIFF_PATH, filename)
            if not os.path.isfile(local_file_path):
                download_file(ftp, input_file, local_file_path)
            epsg_code = check_epsg_code(local_file_path)
            if epsg_code == 0:
                cursor = conn.cursor()
                route_to_db(cursor)
                cursor.execute("UPDATE avt_task SET task_stat = 0, task_message = 'Không đúng định dạng ảnh tiff EPSG',"
                               "updated_at = %s WHERE id = %s", (get_time(), id))
                conn.commit()
                return False
            elif epsg_code != 4326:
                converted_input_files_local = local_file_path.split(".")[0] + "_4326.tif"
                convert_epsg_4326(local_file_path, converted_input_files_local)
                local_file_path = converted_input_files_local
            date_create = get_time_string()
            output_image_name = "result_crop_polygon_" + format(date_create) + ".tif"
            output_path = os.path.join(LOCAL_RESULT_CROP_POLYGON_TIFF_PATH, output_image_name)
            editing_tool = Editing_Tool()
            editing_tool.crop_polygon_tiff(local_file_path, output_path, polygon)
            ftp_dir = FTP_CROP_POLYGON_TIFF_PATH
            ftp.cwd(str(ftp_dir))
            save_dir = ftp_dir + "/" + output_image_name
            task_output = str({
                "output_image": [save_dir]
            }).replace("'", "\"")
            with open(output_path, "rb") as file:
                ftp.storbinary(f"STOR {save_dir}", file)
            ftp.sendcmd(f'SITE CHMOD 775 {save_dir}')
            # owner_group = 'avtadmin:avtadmin'
            # chown_command = f'SITE CHOWN {owner_group} {save_dir}'
            # ftp.sendcmd(chown_command)
            # print("Connection closed")
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 1, task_output = %s, updated_at = %s WHERE id = %s",
                           (task_output, get_time(), id,))
            conn.commit()
            return True
        except ftplib.all_errors as e:
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 0, task_message = 'Lỗi đầu vào' WHERE id = %s", (id,))
            conn.commit()
            # print(f"FTP error: {e}")
            return False

    def stack_tiffs(self, conn, id, task_param, config_data):
        input_files = task_param['input_files']
        try:
            ftp = connect_ftp(config_data)
            input_files_local = []
            for input_file in input_files:
                filename = input_file.split("/")[-1]
                local_file_path = os.path.join(LOCAL_SRC_STACK_TIFF_PATH, filename)
                input_files_local.append(local_file_path)
                if not os.path.isfile(local_file_path):
                    download_file(ftp, input_file, local_file_path)
            for i in range(len(input_files_local)):
                epsg_code = check_epsg_code(input_files_local[i])
                if epsg_code == 0:
                    cursor = conn.cursor()
                    route_to_db(cursor)
                    cursor.execute("UPDATE avt_task SET task_stat = 0 AND task_message = 'EPSG ERROR' WHERE id = %s",
                                   (id,))
                    conn.commit()
                    return False
                elif epsg_code != 4326:
                    converted_input_file_local = input_files_local[i].split(".")[0] + "_4326.tif"
                    convert_epsg_4326(input_files_local[i], converted_input_file_local)
                    input_files_local[i] = converted_input_file_local
            date_create = get_time_string()
            output_image_name = "result_stack_" + format(date_create) + ".tif"
            output_path = os.path.join(LOCAL_RESULT_STACK_TIFF_PATH, output_image_name)
            editing_tool = Editing_Tool()
            images_with_date = editing_tool.stack_tiff(input_files_local, output_path)
            ftp_dir = FTP_STACK_TIFF_PATH
            ftp.cwd(str(ftp_dir))
            save_dir = ftp_dir + "/" + output_image_name
            task_output = str({
                "output_image": [save_dir],
                "time_sorted_images": images_with_date
            }).replace("'", "\"")
            with open(output_path, "rb") as file:
                ftp.storbinary(f"STOR {save_dir}", file)
            ftp.sendcmd(f'SITE CHMOD 775 {save_dir}')
            # owner_group = 'avtadmin:avtadmin'
            # chown_command = f'SITE CHOWN {owner_group} {save_dir}'
            # ftp.sendcmd(chown_command)
            # print("Connection closed")
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 1, task_output = %s, updated_at = %s WHERE id = %s",
                           (task_output, get_time(), id,))
            conn.commit()
            return True
        except ftplib.all_errors as e:
            cursor = conn.cursor()
            route_to_db(cursor)
            cursor.execute("UPDATE avt_task SET task_stat = 0, task_message = 'Lỗi đầu vào' WHERE id = %s", (id,))
            conn.commit()
            # print(f"FTP error: {e}")
            return False

    def process(self, id, config_data):
        conn = psycopg2.connect(
            dbname=config_data['database']['database'],
            user=config_data['database']['user'],
            password=config_data['database']['password'],
            host=config_data['database']['host'],
            port=config_data['database']['port']
        )
        task_stat_value_holder = {'value': 2}
        stop_event = threading.Event()
        checker_thread = threading.Thread(target=check_and_update, args=(id, task_stat_value_holder, conn, stop_event))
        checker_thread.start()
        try:
            cursor = conn.cursor()
            cursor.execute('SET search_path TO public')
            cursor.execute("SELECT current_schema()")
            cursor.execute("SELECT task_param FROM avt_task WHERE id = %s", (id,))
            result = cursor.fetchone()
            task_param = json.loads(result[0])
            algorithm = task_param["algorithm"]
            return_flag = False
            if algorithm == "ghep_anh":
                return_flag = self.merge_tiffs(conn, id, task_param, config_data)
            elif algorithm == "cat_anh":
                return_flag = self.crop_tiff_image(conn, id, task_param, config_data)
            elif algorithm == "cat_da_giac":
                return_flag = self.crop_polygon_tiff(conn, id, task_param, config_data)
            elif algorithm == "xep_chong":
                return_flag = self.stack_tiffs(conn, id, task_param, config_data)
            cursor.close()
            if return_flag:
                task_stat_value_holder['value'] = 1
            else:
                task_stat_value_holder['value'] = 0
        except Exception as e:
            task_stat_value_holder['value'] = 0
        stop_event.set()
        update_database(id, task_stat_value_holder['value'], conn)
        checker_thread.join()
