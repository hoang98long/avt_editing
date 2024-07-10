import rasterio
from rasterio.merge import merge


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
