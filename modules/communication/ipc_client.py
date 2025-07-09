import socket
import select
import asyncio

def check_existing_instance(port, key):
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(10)  # タイムアウトを設定する
        try:
            client_socket.connect(("localhost", port))
            client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            response = client_socket.recv(96).decode("utf-8")
            client_socket.close()
            # 既に起動しているインスタンスが存在する
            if response == key: # 完全に一致
                return True
            else:
                print("Another instance for New target")
                return False
        except ConnectionRefusedError:
            print("First instance")
            return False  # 起動していないインスタンス
        except socket.timeout:
            print("check_existing_instance timeout")
            return False  # 起動していないインスタンス
    except socket.error:
        print("check_existing_instance error")
        return False  # エラーが発生した場合も起動していないインスタンス

# async def async_check_existing_instance(port, key):
#    try:
#        reader, writer = await asyncio.open_connection('localhost', port)
#
#        writer.write(key.encode())
#        await writer.drain()
#
#        response = await reader.read(1024)
#        writer.close()
#        await writer.wait_closed()
#
#        if response.decode() == key:
#            return True
#        else:
#            return False
#
#    except ConnectionRefusedError:
#        return False
#    except socket.timeout:
#        return False
#    except Exception:
#        return False
