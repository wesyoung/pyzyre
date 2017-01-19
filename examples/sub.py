import sys
import zmq

topicfilter = sys.argv[1]

# Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect ("tcp://localhost:%s" % 5001)

socket.setsockopt(zmq.SUBSCRIBE, topicfilter)

control = context.socket(zmq.PUSH)
control.connect("tcp://localhost:%s" % 5002)
control.send_multipart(["SUB", topicfilter]) #needs to be done periodically

while True:
    topic, messagedata = socket.recv_multipart()
    print topic, messagedata
