import os
import sys
import signal
import argparse
import asyncio
import threading
import json
from PIL import Image, ImageDraw
try:
    import pystray
except Exception:  # noqa: W0703
    pystray = None
from modules.communication.udp_client import DelayedUDPSender, hello_server
from modules.communication.ipc_client import check_existing_instance
from modules.communication.ipc_server import start_server


# プロセスサーバのタスクハンドルを保持する変数
server_task = None

# トレイアイコンのインスタンスを保持する変数
tray_icon = None


def _create_image():
    """Tray icon image."""
    image = Image.new('RGB', (64, 64), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 56, 56), fill=(0, 128, 255))
    return image


def setup_tray(exit_callback, settings):
    """Start system tray icon with settings submenu."""
    if pystray is None:
        return None
    icon = pystray.Icon('textCropping', _create_image(), 'textCropping')

    settings_menu = pystray.Menu(
        pystray.MenuItem(
            f"OSC {settings['ip']}:{settings['port']}", None, enabled=False),
    )

    icon.menu = pystray.Menu(
        pystray.MenuItem('設定', settings_menu),
        pystray.MenuItem('Exit', lambda: exit_callback('[Exit] Tray')),
    )

    threading.Thread(target=icon.run, daemon=True).start()
    return icon


async def main(args):
    try:
        # プロセスサーバのタスクを開始する
        global server_task
        server_task = asyncio.create_task(start_server(12321, path))

        # プロセスサーバのタスクが完了するまで待機する
        await server_task

    except asyncio.CancelledError:
        # プロセスサーバのタスクがキャンセルされた場合の処理
        pass
    finally:
        # プロセスサーバのクリーンアップ処理（必要な場合は実装）
        pass


if __name__ == "__main__":
    # 引数 --exclude_subdirectories が指定された場合、ルートディレクトリのみが監視されます。引数が指定されていない場合、サブディレクトリも監視します。
    parser = argparse.ArgumentParser(
        description='Monitor a directory and create thumbnails for video files.')
    args = parser.parse_args()

    # Detect console availability. If no TTY is attached,
    # force --no_console mode so that ainput() is not used.
    if not sys.stdin or not sys.stdin.isatty():
        if not args.no_console:
            print("Console not attached. Disabling console input.")
        args.no_console = True

    args.single_instance_only = args.single_instance_only.lower() == 'true'
    config = {}
    if os.path.isfile(args.config):
        with open(args.config, 'r', encoding='utf-8') as f:
            try:
                config = json.load(f)
            except Exception:
                config = {}    # 設定ファイルの値で上書きし、さらに起動引数があればそちらを優先
    for key in []:
        if getattr(args, key) == parser.get_default(key) and key in config:
            setattr(args, key, config[key])

    if isinstance(args.single_instance_only, str):
        args.single_instance_only = args.single_instance_only.lower() == 'true'

    # 既に起動しているインスタンスをチェックする
    if not args.single_instance_only and check_existing_instance(12321, path):
        print("既に起動しています。")
        sys.exit(0)

    # サーバーとの通信を試みる
    response = hello_server(path)
    if not args.single_instance_only and response is not None:
        print("Hello OSC: " + response)
        if response == "overlapping":
            # remove_pid_file()
            sys.exit("[Exit] Overlapping")

    def exit_handler(reason):
        global tray_icon, server_task
        print(f"終了処理を開始します: {reason}")

        # トレイアイコンを停止
        if tray_icon:
            print("トレイアイコンを停止します")
            tray_icon.stop()

        # サーバータスクをキャンセル
        if server_task:
            print("サーバータスクをキャンセルします")
            server_task.cancel()

        sys.exit()

    # プログラムが終了する際に呼び出されるハンドラを登録する
    # atexit.register(exit_handler("[Exit] Normal"))

    # Ctrl+Cなどのシグナルハンドラを登録する
    def exit_wrapper(reason):
        return lambda sig, frame: exit_handler(reason)
    signal.signal(signal.SIGINT, exit_wrapper("[Exit] Signal Interrupt"))

    # タスクトレイアイコンを表示する
    tray_icon = setup_tray(exit_handler, settings)    # アプリケーションのメイン処理
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        # 例外処理
        exit_handler("[Exit] Keyboard Interrupt")
