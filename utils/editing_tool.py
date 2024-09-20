import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
from shapely.geometry import Polygon, box
# from shapely.geometry.polygon import orient
import os
from datetime import datetime
from itertools import combinations



def get_date_modified(file_path):
    timestamp = os.path.getmtime(file_path)
    date_modified = datetime.fromtimestamp(timestamp)
    return date_modified


def sort_tiffs_by_date(tiff_paths):
    tiffs_with_dates = [(path, get_date_modified(path)) for path in tiff_paths]
    tiffs_with_dates.sort(key=lambda x: x[1], reverse=True)
    # sorted_tiff_paths = [path for path, _ in tiffs_with_dates]
    return tiffs_with_dates


def intersect_detect_two_images(image1_path, image2_path):
    with rasterio.open(image1_path) as src1, rasterio.open(image2_path) as src2:
        bounds1 = src1.bounds
        bounds2 = src2.bounds

        geom1 = box(bounds1.left, bounds1.bottom, bounds1.right, bounds1.top)
        geom2 = box(bounds2.left, bounds2.bottom, bounds2.right, bounds2.top)

        intersection = geom1.intersection(geom2)

        if not intersection.is_empty:
            intersection_bounds = intersection.bounds
            intersection_width = intersection_bounds[2] - intersection_bounds[0]
            intersection_height = intersection_bounds[3] - intersection_bounds[1]

            if intersection_width > 0 and intersection_height > 0:
                polygon = [
                    [intersection_bounds[0], intersection_bounds[1]],  # [xmin, ymin]
                    [intersection_bounds[0], intersection_bounds[3]],  # [xmin, ymax]
                    [intersection_bounds[2], intersection_bounds[3]],  # [xmax, ymax]
                    [intersection_bounds[2], intersection_bounds[1]],  # [xmax, ymin]
                    [intersection_bounds[0], intersection_bounds[1]]
                ]
                return polygon

    return None


def intersect_detect(image_files):
    intersections = []
    for image1_path, image2_path in combinations(image_files, 2):
        polygon = intersect_detect_two_images(image1_path, image2_path)
        if polygon:
            intersections.append(polygon)
        else:
            pass
    return intersections


class Editing_Tool:
    def __init__(self):
        pass

    def merge_tiffs(self, tiff_files, output_path):
        src_files_to_mosaic = [rasterio.open(fp) for fp in tiff_files]
        mosaic, out_trans = merge(src_files_to_mosaic)
        out_meta = src_files_to_mosaic[0].meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_trans
        })

        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(mosaic)
        intersections = intersect_detect(tiff_files)
        return intersections

    def crop_tiff_image(self, input_tiff_path, output_tiff_path, xmin, ymin, xmax, ymax):
        with rasterio.open(input_tiff_path) as src:
            # Get the transform and inverse transform from the image
            transform = src.transform
            inv_transform = ~transform

            # Convert geographical coordinates to pixel indices
            top_left = inv_transform * (xmin, ymax)  # ymax for top
            bottom_right = inv_transform * (xmax, ymin)  # ymin for bottom

            # Convert to integer pixel indices
            x1, y1 = map(int, map(round, top_left))
            x2, y2 = map(int, map(round, bottom_right))

            # Ensure that y1 is less than y2 for correct window slicing
            if y1 > y2:
                y1, y2 = y2, y1

            # Read the image data within the window
            window = rasterio.windows.Window.from_slices((y1, y2), (x1, x2))
            image = src.read(window=window)
            profile = src.profile

            # Update the profile with new width, height, and transform
            new_transform = rasterio.windows.transform(window, transform)
            profile.update({
                'height': y2 - y1,
                'width': x2 - x1,
                'transform': new_transform
            })

            # Write the cropped image to a new TIFF file
            with rasterio.open(output_tiff_path, 'w', **profile) as dst:
                dst.write(image)

    def crop_polygon_tiff(self, tiff_path, output_path, polygon_coords):
        with rasterio.open(tiff_path) as src:
            polygon = Polygon(polygon_coords)
            # oriented_polygon = orient(polygon, sign=1.0)
            out_image, out_transform = mask(src, [polygon], crop=True)
            out_meta = src.meta.copy()
            out_meta.update({"driver": "GTiff",
                             "height": out_image.shape[1],
                             "width": out_image.shape[2],
                             "transform": out_transform})
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(out_image)

    def stack_tiff(self, tiff_paths, output_path):
        tiffs_with_dates = sort_tiffs_by_date(tiff_paths)
        sorted_tiff_paths = [path for path, _ in tiffs_with_dates]
        self.merge_tiffs(sorted_tiff_paths, output_path)
        return tiffs_with_dates
