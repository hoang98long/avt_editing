FROM python:3.8 as requirements-stage

WORKDIR /app

COPY /home/avt/avt_editing /app/avt_editing

RUN chmod +x /app/avt_editing/main.exe

CMD ["./avt_editing/main.exe"]