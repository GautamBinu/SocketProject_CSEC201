#THIS IS A TEST SERVER.

import socket, struct

def send(c, text):
    data = text.encode()
    c.sendall(struct.pack("!I", len(data)) + data)

def recv_exact(c, n):
    buf = b""
    while len(buf) < n:
        chunk = c.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def recv(c):
    head = recv_exact(c, 4)
    if head is None:
        return None
    (length,) = struct.unpack("!I", head)
    body = recv_exact(c, length)
    return body.decode() if body else None

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 9009))
srv.listen(1)
print("stub server on 127.0.0.1:9009")

conn, _ = srv.accept()
while True:
    msg = recv(conn)
    if msg is None or msg == "End":
        print("server: client ended")
        break
    print("server got:", msg)
    if msg.startswith("SS,"):
        send(conn, "CC")
    elif msg.startswith("CM,openRead,"):
        name = msg.split(",", 2)[2]
        if name == "data.txt":
            send(conn, "SC,hello from the server\nsecond line")
        else:
            send(conn, "EE,404,file not found")
    else:
        send(conn, "EE,400,unsupported")
conn.close()
srv.close()
