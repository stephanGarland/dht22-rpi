FROM python:3.7-slim-buster
WORKDIR /usr/src
RUN apt update && apt install -y gcc make python3-setuptools unzip
ADD https://github.com/joan2937/pigpio/archive/master.zip ./
RUN unzip /usr/src/master.zip
RUN make -C ./pigpio-master && make install -C ./pigpio-master

COPY requirements.txt ./

RUN pip install -r requirements.txt
ENV IS_DOCKER True
WORKDIR /home
COPY DHT22.py ./
COPY main.sh ./

CMD [ "/bin/sh", "main.sh" ]
