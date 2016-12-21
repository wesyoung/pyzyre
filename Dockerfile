FROM ubuntu:trusty
MAINTAINER wesyoung <wes@barely3am.com>

RUN DEBIAN_FRONTEND=noninteractive apt-get update -y -q
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y -q build-essential git-core libtool autotools-dev autoconf \
automake pkg-config cmake uuid-dev cython python-pip

RUN pip install pip --upgrade
RUN pip install -U wheel setuptools cython

COPY . /build

WORKDIR /build

# cleanup from the copy [todo- finish setup.py clean -a]
RUN rm -rf bundled/* build/* czmq zyre dist/*
RUN rm -rf `find . | grep pycache`
RUN rm -rf `find . | fgrep .pyc`

# build and install
RUN pip install -r dev_requirements.txt
RUN python setup.py build_ext bdist_wheel
RUN pip install dist/*.whl

# tests get confused if these are in the local directory given how we generate the bindings and run the tests
RUN rm -rf zyre czmq
RUN python setup.py test