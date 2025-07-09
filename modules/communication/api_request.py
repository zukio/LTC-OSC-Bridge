import requests
import pickle
from threading import Timer

def send(url, message):
    try:
        # オブジェクトをバイト列に変換（シリアライズ）します
        data = pickle.dumps(message)
        # POSTリクエストを送信します
        response = requests.post(url, data=data)
        # レスポンスのステータスコードを確認します
        if response.status_code == 200:
            print("API request succeeded")
        else:
            print("API request failed:", response.status_code)
    except Exception as e:
        print('Error in API request:', e)

# 最初の更新から指定した遅延時間（ここでは 1 秒）が経過するまで無更新状態が続いた時点で、一度だけAPIリクエストが送信されます。
class DelayedAPISender:
    def __init__(self, delay=1):
        self.delay = delay
        self.timer = None

    def send_message(self, url, message):
        if self.timer is not None:
            self.timer.cancel()

        self.timer = Timer(self.delay, send, [url, message])
        self.timer.start()
