from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Thu thập tất cả các tệp dữ liệu của rasterio
datas = collect_data_files('rasterio')

# Thu thập tất cả các thư viện động (DLL, SO) của rasterio
binaries = collect_dynamic_libs('rasterio')