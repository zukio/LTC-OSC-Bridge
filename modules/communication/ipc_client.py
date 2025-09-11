"""IPC client for checking existing instances."""
import socket
import logging


def check_existing_instance(port: int, key: str) -> bool:
    """Check if another instance is already running.

    Args:
        port: Port to check
        key: Application key to send

    Returns:
        True if instance exists, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            sock.connect(("127.0.0.1", port))
            sock.send(key.encode("utf-8"))
            response = sock.recv(1024).decode("utf-8")
            return response == "OK"
    except (socket.error, ConnectionRefusedError, OSError):
        return False
    except Exception as e:
        logging.warning("Error checking existing instance: %s", e)
        return False
