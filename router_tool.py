"""Task-scoped SSH transport; all credentials are read from environment variables."""
import argparse
import os
import pathlib
import select
import shlex
import socket
import struct
import sys
import time

import paramiko


def connect():
    client = paramiko.SSHClient()
    client.load_system_host_keys(str(pathlib.Path.home() / ".ssh" / "known_hosts"))
    task_socket = None
    if os.environ.get('ROUTER_TASK_INTERFACE_INDEX'):
        # Per-socket Windows interface selection, without changing system routes/TUN.
        task_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        task_socket.settimeout(10)
        task_socket.setsockopt(socket.IPPROTO_IP, 31, struct.pack(
            '!I', int(os.environ['ROUTER_TASK_INTERFACE_INDEX'])))
        task_socket.connect((os.environ.get('ROUTER_TASK_CONNECT_ADDRESS',
                            os.environ.get('ROUTER_TASK_HOST', '192.168.11.1')), 22))
    client.connect(
        os.environ.get('ROUTER_TASK_HOST', '192.168.11.1'),
        username=os.environ.get('ROUTER_TASK_USERNAME', 'root'),
        password=os.environ["ROUTER_TASK_PASSWORD"],
        look_for_keys=False, allow_agent=False, timeout=10, sock=task_socket,
    )
    return client


def execute(client, command, output=None):
    _, stdout, _ = client.exec_command(command, timeout=600)
    ch = stdout.channel
    while not ch.exit_status_ready() or ch.recv_ready() or ch.recv_stderr_ready():
        if ch.recv_ready():
            block = ch.recv(65536)
            (output or sys.stdout.buffer).write(block)
            (output or sys.stdout.buffer).flush()
        if ch.recv_stderr_ready():
            sys.stderr.buffer.write(ch.recv_stderr(65536))
            sys.stderr.buffer.flush()
        if not ch.recv_ready() and not ch.recv_stderr_ready():
            select.select([ch], [], [], 0.2)
    return ch.recv_exit_status()


def put(client, local, remote, mode):
    stdin, stdout, stderr = client.exec_command("cat > " + shlex.quote(remote + ".new"))
    with open(local, "rb") as f:
        while block := f.read(1024 * 1024):
            stdin.write(block)
    stdin.channel.shutdown_write()
    status = stdout.channel.recv_exit_status()
    if status:
        raise RuntimeError("SSH upload failed")
    status = execute(client, "chmod " + mode + " " + shlex.quote(remote + ".new") +
                     " && mv -f " + shlex.quote(remote + ".new") + " " + shlex.quote(remote))
    if status:
        raise RuntimeError("SSH atomic install failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["exec", "put", "get"])
    parser.add_argument("path", nargs="?")
    parser.add_argument("remote", nargs="?")
    parser.add_argument("--mode", default="644")
    args = parser.parse_args()
    client = connect()
    try:
        if args.action == "exec":
            command = os.environ["ROUTER_TASK_COMMAND"]
            return execute(client, command)
        if args.action == "put":
            put(client, args.path, args.remote, args.mode)
            print("installed=" + args.remote)
            return 0
        if args.action == "get":
            with open(args.path, "wb") as f:
                return execute(client, "cat " + shlex.quote(args.remote), f)
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
