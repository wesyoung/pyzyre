import sys
import zmq

topic = sys.argv[1]

# Socket to talk to server
context = zmq.Context()
control = context.socket(zmq.PUSH)
control.connect("tcp://localhost:%s" % 5002)
control.send_multipart(["SUB", topic])

while True:
    msg = sys.stdin.readline().rstrip()
    if not msg:
        break
    control.send_multipart(["PUB", topic, msg])
