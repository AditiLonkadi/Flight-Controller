import socket
import time
import random

host = 'localhost'
port = 5051  # ✅ Updated port

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    sock.connect((host, port))
    print(f"Connected to Unity on {host}:{port}")

    while True:
        roll = round(random.uniform(-1, 1), 2)
        pitch = round(random.uniform(-1, 1), 2)
        yaw = round(random.uniform(-1, 1), 2)
        throttle = round(random.uniform(0, 5), 2)

        data = f"{roll},{pitch},{yaw},{throttle}"
        sock.sendall(data.encode('utf-8'))
        time.sleep(0.1)

except ConnectionRefusedError:
    print("Connection refused. Is the Unity server running?")
finally:
    sock.close()
