"""
Thread Pool Module
Manage background threads for transcription
"""

from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any


class ThreadPool:
    """Thread pool for background tasks"""
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = []
    
    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """Submit a task to the pool"""
        future = self.executor.submit(fn, *args, **kwargs)
        self.futures.append(future)
        return future
    
    def wait_all(self):
        """Wait for all tasks to complete"""
        for future in self.futures:
            future.result()
        self.futures.clear()
    
    def shutdown(self):
        """Shutdown the thread pool"""
        self.executor.shutdown(wait=True)
