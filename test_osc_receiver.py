#!/usr/bin/env python3
"""
Simple OSC receiver to test LTC-OSC-Bridge messages
"""

import argparse
from pythonosc import dispatcher
from pythonosc import osc_server
import threading


def ltc_decode_handler(unused_addr, timecode):
    """Handle LTC decode messages"""
    print(f"LTC Decode: {timecode}")


def status_running_handler(unused_addr, timecode):
    """Handle running status messages"""
    print(f"Status: running | Timecode: {timecode}")


def status_paused_handler(unused_addr, timecode):
    """Handle paused status messages"""
    print(f"Status: paused | Timecode: {timecode}")


def status_reset_handler(unused_addr, timecode):
    """Handle reset status messages"""
    print(f"Status: reset | Timecode: {timecode}")


def status_stopped_handler(unused_addr, timecode):
    """Handle stopped status messages"""
    print(f"Status: stopped | Timecode: {timecode}")


def legacy_ltc_handler(unused_addr, timecode):
    """Handle legacy LTC messages (for compatibility)"""
    print(f"LTC (legacy): {timecode}")


def legacy_status_handler(unused_addr, *args):
    """Handle legacy status messages (for compatibility)"""
    if len(args) == 2:
        status, timecode = args
        print(f"Status (legacy): {status} | Timecode: {timecode}")
    else:
        print(f"Status (legacy): {args[0]}")


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

    # New v2.0 address scheme
    dispatcher_obj.map(args.address + "/decode", ltc_decode_handler)
    dispatcher_obj.map(args.address + "/status-running",
                       status_running_handler)
    dispatcher_obj.map(args.address + "/status-paused",
                       status_paused_handler)
    dispatcher_obj.map(args.address + "/status-reset",
                       status_reset_handler)
    dispatcher_obj.map(args.address + "/status-stopped",
                       status_stopped_handler)

    # Legacy v1.x compatibility
    dispatcher_obj.map(args.address, legacy_ltc_handler)
    dispatcher_obj.map(args.address + "/status", legacy_status_handler)

    server = osc_server.ThreadingOSCUDPServer(
        (args.ip, args.port), dispatcher_obj)
    print(f"Listening for OSC messages on {args.ip}:{args.port}")
    print(f"New v2.0 addresses:")
    print(f"  Decode: {args.address}/decode")
    print(f"  Running: {args.address}/status-running")
    print(f"  Paused: {args.address}/status-paused")
    print(f"  Reset: {args.address}/status-reset")
    print(f"  Stopped: {args.address}/status-stopped")
    print(f"Legacy v1.x addresses (for compatibility):")
    print(f"  LTC: {args.address}")
    print(f"  Status: {args.address}/status")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
