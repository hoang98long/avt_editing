FROM continuumio/miniconda3

WORKDIR /app

RUN apt-get update && apt-get install -y libgl1-mesa-glx

COPY . /app/avt_editing

RUN conda create --name avt_editing python=3.8  # Thay python=3.8 bằng phiên bản Python mà bạn cần
RUN echo "conda activate avt_editing" >> ~/.bashrc
RUN conda init bash

COPY requirements.txt .
RUN conda run -n avt_editing pip install -r requirements.txt
RUN conda install -n avt_editing -c conda-forge gdal
RUN conda install -n avt_editing -c conda-forge rasterio

CMD ["bash", "-c", "source activate avt_editing && cd /app/avt_editing && python main.py"]