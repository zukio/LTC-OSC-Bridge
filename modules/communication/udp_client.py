import socket
import pickle
from threading import Timer

def send(message, port=12345, server_address='localhost'):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # オブジェクトをバイト列に変換（シリアライズ）します
        data = pickle.dumps(message)
        sock.sendto(data, (server_address, port))
    finally:
        sock.close()

def hello_server(message, port=12345, server_address='localhost'):
    # 既に起動しているインスタンスとの通信を試みる
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((server_address, port))  # 既存のインスタンスと通信するポート番号に合わせて適宜変更してください
        sock.sendall(message.encode())
        response = sock.recv(1024).decode()
        sock.close()
        return response.strip()  # 既存のインスタンスからのレスポンスを返す
    except ConnectionRefusedError:
        return None  # 通信ができなかった場合、既存のインスタンスは存在しないと判断


# 最初の更新から指定した遅延時間（ここでは 1 秒）が経過するまで無更新状態が続いた時点で、一度だけUDPが送信されます。
class DelayedUDPSender:
    def __init__(self, delay=1):
        self.delay = delay
        self.timer = None

    def send_message(self, ip, port, message):
        if self.timer is not None:
            self.timer.cancel()

        self.timer = Timer(self.delay, send, [message, port, ip])
        self.timer.start()
