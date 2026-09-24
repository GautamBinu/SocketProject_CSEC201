#THIS IS A TEST SERVER. DO NOT SUBMIT THIS SHII
from datetime import datetime
import socket
import time

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

host = "127.0.0.1"
port = 9009

s.bind((host, port))
s.listen()

print("Server listening on port: " + str(port))

while True:
	clientS, clientAddr = s.accept()
	print("Received connection from %s" % str(clientAddr))
	while True:
		mesEnc = clientS.recv(2048)
		msg = mesEnc.decode("utf-8")
		print("C: " + msg)

		if msg == ".":
			break
	clientS.close()
