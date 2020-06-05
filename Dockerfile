FROM python:3.7-slim-buster AS builder
WORKDIR /usr/src
RUN apt update && apt install -y gcc make python3-setuptools unzip
ADD https://github.com/joan2937/pigpio/archive/master.zip /usr/src
RUN unzip /usr/src/master.zip
RUN make -C ./pigpio-master && make install -C ./pigpio-master

COPY requirements.txt ./
COPY DHT22.py ./
COPY main.sh ./

RUN pip install -r requirements.txt
ENV IS_DOCKER True

CMD [ "/bin/bash", "main.sh" ]
