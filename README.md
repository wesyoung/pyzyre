# pyzyre
Higher level pythonic bindings for Zyre (using czmq and zyre bindings).

# Getting Started
* build_ext will fetch and build libzmq, czmq and zyre to be embedded with the package
* requires pyzmq>16.0

```bash
$ git clone https://github.com/wesyoung/pyzyre.git
$ pip install -r requirements.txt
$ python setup.py build_ext bdist_wheel
$ pip install dist/*
$ zyre-chat -h
$ zyre-chat -d
```
