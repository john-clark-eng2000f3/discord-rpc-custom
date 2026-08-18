import asyncio
import json
import struct

OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2
OP_PING = 3
OP_PONG = 4

class DiscordIPC:
    """Low-level Windows Named Pipe client for Discord IPC."""
    
    def __init__(self):
        self._handle = None

    async def connect(self):
        for i in range(10):
            pipe_path = f"\\\\.\\pipe\\discord-ipc-{i}"
            try:
                # Named pipes on Windows can be opened directly as binary files
                self._handle = await asyncio.to_thread(open, pipe_path, "r+b", buffering=0)
                return
            except (FileNotFoundError, PermissionError):
                continue
        raise RuntimeError("Discord IPC pipe not found. Is Discord running?")

    async def send(self, op: int, payload: dict):
        # print(f"DEBUG: sending op {op}: {payload}")
        data = json.dumps(payload).encode("utf-8")
        header = struct.pack("<II", op, len(data))
        try:
            await asyncio.to_thread(self._handle.write, header + data)
        except OSError as e:
            # Windows error 22 is invalid argument (often thrown when pipe closed), 109 is broken pipe
            if e.errno in (22, 109, 232):
                raise ConnectionResetError("Failed to write to Discord pipe") from e
            raise

    async def _read_exactly(self, n: int) -> bytes:
        def read_op():
            chunks = []
            bytes_left = n
            while bytes_left > 0:
                try:
                    chunk = self._handle.read(bytes_left)
                except OSError as e:
                    if e.errno in (22, 109, 232):
                        raise ConnectionResetError("Discord pipe closed") from e
                    raise
                if not chunk:
                    raise ConnectionResetError("Discord pipe reached EOF")
                chunks.append(chunk)
                bytes_left -= len(chunk)
            return b"".join(chunks)

        return await asyncio.to_thread(read_op)

    async def recv(self):
        header = await self._read_exactly(8)
        op, length = struct.unpack("<II", header)
        payload_data = await self._read_exactly(length)
        return op, json.loads(payload_data.decode("utf-8"))

    async def close(self):
        if self._handle:
            try:
                await asyncio.to_thread(self._handle.close)
            except OSError:
                pass
            self._handle = None
