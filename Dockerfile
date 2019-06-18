FROM python:3.6-slim-stretch
MAINTAINER wesyoung <wes@barely3am.com>

RUN echo "deb http://http.debian.net/debian/ stretch main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://http.debian.net/debian/ stretch-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://security.debian.org/ stretch/updates main contrib non-free" >> /etc/apt/sources.list

RUN DEBIAN_FRONTEND=noninteractive apt-get update -y -q
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y -q build-essential git-core libtool autotools-dev autoconf \
automake pkg-config cmake uuid-dev cython python-pip libsystemd-dev vim net-tools

#RUN pip install pip --upgrade
#RUN pip install -U wheel setuptools cython

#COPY . /build

COPY zeromq-4.3.1.tar.gz /build/libzmq.tar.gz
COPY czmq-4.2.0.tar.gz /build/czmq.tar.gz
COPY zyre.tar.gz /build/zyre.tar.gz

WORKDIR /build

RUN mkdir libzmq && tar -zxvf libzmq.tar.gz --strip-components=1 -C libzmq
WORKDIR libzmq
RUN ./configure && make install

WORKDIR /build
RUN mkdir czmq && tar -zxvf czmq.tar.gz --strip-components=1 -C czmq
WORKDIR czmq
RUN ./configure --enable-bindings-python --enable-drafts && make install
WORKDIR bindings/python
RUN python3 setup.py install

WORKDIR /build
RUN mkdir zyre && tar -zxvf zyre.tar.gz --strip-components=1 -C zyre
WORKDIR zyre
RUN bash autogen.sh && ./configure --enable-bindings-python --enable-drafts && make check && make install
WORKDIR bindings/python
RUN python3 setup.py install

RUN ldconfig

WORKDIR /
COPY dev_requirements.txt /build
COPY requirements.txt /build

RUN pip3 install 'Cython>=0.20'
WORKDIR /build
RUN pip3 install -r dev_requirements.txt
COPY dist/pyzyre-*.tar.gz /build/pyzyre.tar.gz
RUN mkdir pyzyre && tar -zxvf pyzyre.tar.gz --strip-components=1 -C pyzyre
WORKDIR pyzyre
RUN python3 setup.py install
RUN python3 setup.py test

WORKDIR /

ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE

EXPOSE 49150/tcp
EXPOSE 49151/tcp
EXPOSE 49152/tcp
EXPOSE 49153/tcp
EXPOSE 49154/tcp
EXPOSE 49155/tcp

RUN apt-get clean && dpkg -r build-essential && rm -rf /root/.cache && \
    rm -rf /var/lib/apt/lists/*

#CMD zyre-chat -d
#CMD sleep 3000
CMD /bin/bash

#COPY dist/*.tar.gz .

# cleanup from the copy [todo- finish setup.py clean -a]
#RUN rm -rf bundled/* build/* czmq zyre dist/*
#RUN rm -rf `find . | grep pycache`
#RUN rm -rf `find . | fgrep .pyc`
#
# build and install
#RUN pip install -r dev_requirements.txt
#RUN python setup.py build_ext bdist_wheel
#RUN pip install dist/*.whl
#
# tests get confused if these are in the local directory given how we generate the bindings and run the tests
#RUN rm -rf zyre czmq
#RUN python setup.py test