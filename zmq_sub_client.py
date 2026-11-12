import argparse
import json
from typing import Optional, Tuple

import numpy as np
import zmq


def create_sub_socket(
    connect_address: str = "tcp://127.0.0.1:5556",
    topic: str = "frame",
    conflate: bool = False,
    rcvhwm: int = 60,
) -> zmq.Socket:
    """Create and connect a ZMQ SUB socket subscribed to `topic`."""
    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.RCVHWM, rcvhwm)
    if conflate:
        # Note: ZMQ_CONFLATE only supports single-part messages; leave False for multipart
        sub.setsockopt(zmq.CONFLATE, 1)
    sub.connect(connect_address)
    sub.setsockopt(zmq.SUBSCRIBE, topic.encode("utf-8"))
    return sub


def _decode_multipart(parts) -> Tuple[str, dict, np.ndarray]:
    topic_bytes, meta_bytes, frame_buf = parts
    topic = bytes(topic_bytes).decode("utf-8")
    meta = json.loads(bytes(meta_bytes).decode("utf-8"))
    frame = np.frombuffer(frame_buf, dtype=np.dtype(meta["dtype"])).reshape(
        meta["shape"]
    )
    return topic, meta, frame


def recv_frame(
    sub_socket: zmq.Socket, flags: int = 0
) -> Tuple[str, dict, np.ndarray]:
    """
    Receive a multipart frame message `[topic, meta_json, frame_bytes]`
    from `WebcamZmqHW` and reconstruct the numpy array.
    """
    parts = sub_socket.recv_multipart(flags=flags, copy=False)
    return _decode_multipart(parts)


def recv_latest_frame(
    sub_socket: zmq.Socket, timeout_ms: int = 1000
) -> Optional[Tuple[str, dict, np.ndarray]]:
    """
    Drain any queued messages on `sub_socket` and return the newest frame,
    waiting up to `timeout_ms` for the first frame if the queue is empty.
    """
    if sub_socket.poll(timeout_ms, zmq.POLLIN) == 0:
        return None

    latest_parts = sub_socket.recv_multipart(flags=0, copy=False)
    while sub_socket.poll(0, zmq.POLLIN):
        try:
            latest_parts = sub_socket.recv_multipart(flags=zmq.NOBLOCK, copy=False)
        except zmq.Again:
            break
    return _decode_multipart(latest_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Subscribe to WebcamZmqHW ZMQ PUB frame stream."
    )
    parser.add_argument(
        "--address",
        default="tcp://127.0.0.1:5556",
        help="ZMQ publisher address to connect to (default: tcp://127.0.0.1:5556)",
    )
    parser.add_argument(
        "--topic",
        default="frame",
        help="ZMQ subscription topic (default: frame)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of frames to receive before exiting (0 for infinite)",
    )
    args = parser.parse_args()

    sub = create_sub_socket(args.address, args.topic)
    print(f"Subscribed to {args.address} (topic='{args.topic}')...")
    received = 0
    try:
        while args.count == 0 or received < args.count:
            topic, meta, frame = recv_frame(sub)
            received += 1
            print(
                f"[{received}] topic={topic} frame_id={meta['frame_id']} "
                f"shape={frame.shape} dtype={frame.dtype} "
                f"color={meta['color_mode']} mean={frame.mean():.1f}"
            )
    except KeyboardInterrupt:
        pass
    finally:
        sub.close(linger=0)


if __name__ == "__main__":
    main()
