FROM python:3.7-slim-buster
WORKDIR /usr/src
COPY ./requirements.txt /usr/src/requirements.txt
RUN pip install -r requirements.txt
RUN apt update && apt install -y gcc make python3-setuptools unzip
ADD https://github.com/joan2937/pigpio/archive/master.zip /usr/src
RUN unzip /usr/src/master.zip
RUN make -C ./pigpio-master && make install -C ./pigpio-master
COPY ./main.sh /usr/src/main.sh
COPY . /usr/src
CMD [ "/bin/bash", "main.sh" ]
