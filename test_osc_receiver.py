#!/usr/bin/env python3
"""
Simple OSC receiver to test LTC-OSC-Bridge messages
"""

import argparse
from pythonosc import dispatcher
from pythonosc import osc_server
import threading


def ltc_handler(unused_addr, timecode):
    """Handle LTC messages"""
    print(f"LTC: {timecode}")


def status_handler(unused_addr, *args):
    """Handle status messages"""
    if len(args) == 2:
        status, timecode = args
        print(f"Status: {status} | Timecode: {timecode}")
    else:
        print(f"Status: {args[0]} (legacy format)")


def main():
    parser = argparse.ArgumentParser(
        description="Test OSC receiver for LTC-OSC-Bridge")
    parser.add_argument("--ip", default="127.0.0.1", help="IP to listen on")
    parser.add_argument("--port", type=int, default=7000,
                        help="Port to listen on")
    parser.add_argument("--address", default="/ltc",
                        help="OSC address to listen for")

    args = parser.parse_args()

    dispatcher_obj = dispatcher.Dispatcher()
    dispatcher_obj.map(args.address, ltc_handler)
    dispatcher_obj.map(args.address + "/status", status_handler)

    server = osc_server.ThreadingOSCUDPServer(
        (args.ip, args.port), dispatcher_obj)
    print(f"Listening for OSC messages on {args.ip}:{args.port}")
    print(f"LTC address: {args.address}")
    print(f"Status address: {args.address}/status")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
