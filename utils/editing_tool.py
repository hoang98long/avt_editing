import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
from shapely.geometry import Polygon
# from shapely.geometry.polygon import orient


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
