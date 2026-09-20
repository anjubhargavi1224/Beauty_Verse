import asyncio
import threading
import unittest
from backend.services.bounded_work import bounded_call

class BoundedWorkTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_does_not_release_still_running_work(self):
        release=threading.Event()
        def blocked():
            release.wait(2)
        try:
            results=await asyncio.gather(bounded_call(blocked,timeout=.03),bounded_call(blocked,timeout=.03),return_exceptions=True)
            self.assertTrue(all(isinstance(r,TimeoutError) for r in results))
            with self.assertRaises(RuntimeError):await bounded_call(lambda:1,timeout=.1)
        finally:release.set()

if __name__=='__main__':unittest.main()
