"""Bound response latency and in-flight provider work without blocking the event loop."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='beautyverse-provider')
_slots = BoundedSemaphore(2)

async def bounded_call(function, *args, timeout):
    # A timed-out blocking SDK call may continue running. Keep its slot occupied
    # until it actually exits, rather than accumulating background calls.
    if not _slots.acquire(blocking=False):
        raise RuntimeError('External services are still busy.')
    try:
        future = _pool.submit(function, *args)
    except BaseException:
        _slots.release()
        raise
    future.add_done_callback(lambda _: _slots.release())
    return await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout)
