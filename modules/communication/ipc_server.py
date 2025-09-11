"""IPC server for single instance enforcement."""
import asyncio
import logging


async def handle_client(reader, writer, key: str):
    """Handle client connection."""
    try:
        data = await reader.read(1024)
        client_key = data.decode("utf-8")

        if client_key == key:
            writer.write(b"OK")
        else:
            writer.write(b"INVALID")

        await writer.drain()
        writer.close()
        await writer.wait_closed()
    except Exception as e:
        logging.warning("Error handling client: %s", e)
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass


async def start_server(port: int, key: str):
    """Start IPC server for single instance enforcement.

    Args:
        port: Port to listen on
        key: Application key to verify
    """
    try:
        server = await asyncio.start_server(
            lambda r, w: handle_client(r, w, key),
            "127.0.0.1",
            port
        )

        async with server:
            await server.serve_forever()
    except OSError as e:
        if e.errno == 10048:  # Address already in use
            logging.warning("Port %d already in use", port)
        else:
            logging.error("Failed to start IPC server: %s", e)
    except Exception as e:
        logging.error("IPC server error: %s", e)
