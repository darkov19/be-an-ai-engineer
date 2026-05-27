import asyncio
import contextvars
from typing import Dict, Any, Optional, List

# ContextVar to track the active task ID in the current execution context
active_task_id: contextvars.ContextVar[str] = contextvars.ContextVar("active_task_id", default="")

class TaskManager:
    """
    Manages thread-safe/asyncio-safe event queues for active background tasks.
    Enables streaming logs live via SSE and avoids memory leaks by providing
    proper cleanup mechanisms.
    """
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self._active_streams: set = set()
        self._finished_tasks: set = set()

    def register_task(self, task_id: str) -> asyncio.Queue:
        """
        Registers a new task ID and initializes its log queue and history.
        """
        queue = asyncio.Queue()
        self._queues[task_id] = queue
        self._history[task_id] = []
        self._finished_tasks.discard(task_id)
        self._active_streams.discard(task_id)
        return queue

    def get_queue(self, task_id: str) -> Optional[asyncio.Queue]:
        """
        Retrieves the queue for the given task ID.
        """
        return self._queues.get(task_id)

    def get_history(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all accumulated logs for the given task ID.
        """
        return self._history.get(task_id, [])

    def enqueue_log(self, task_id: str, log_data: Dict[str, Any]):
        """
        Thread-safe/async-safe helper to push a log record into a task's queue and history.
        """
        queue = self._queues.get(task_id)
        if queue is not None:
            # Store in history for timeout/debug dumping
            if task_id in self._history:
                self._history[task_id].append(log_data)
            try:
                loop = asyncio.get_running_loop()
                # If running inside an event loop, schedule it thread-safely
                loop.call_soon_threadsafe(queue.put_nowait, log_data)
            except RuntimeError:
                # Fallback if no running loop in current context
                pass

    def start_stream(self, task_id: str):
        """
        Tracks that an SSE client is actively streaming the logs of this task.
        """
        self._active_streams.add(task_id)

    def stop_stream(self, task_id: str):
        """
        Tracks that an SSE client has stopped streaming this task.
        Cleans up if the background task is already finished.
        """
        self._active_streams.discard(task_id)
        if task_id in self._finished_tasks:
            self.cleanup(task_id)

    def finish_task(self, task_id: str):
        """
        Marks the background task as finished.
        Schedules a delayed cleanup if no SSE client is actively streaming,
        allowing late streaming connections to still fetch logs briefly.
        """
        self._finished_tasks.add(task_id)
        if task_id not in self._active_streams:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._delayed_cleanup(task_id))
            except RuntimeError:
                # Fallback if no running loop
                self.cleanup(task_id)

    async def _delayed_cleanup(self, task_id: str, delay: float = 60.0):
        """
        Asynchronously waits before cleaning up the task to handle late client connections.
        """
        await asyncio.sleep(delay)
        if task_id not in self._active_streams:
            self.cleanup(task_id)

    def cleanup(self, task_id: str):
        """
        Cleans up the queue and history registered under task_id to prevent memory leaks.
        """
        self._queues.pop(task_id, None)
        self._history.pop(task_id, None)
        self._finished_tasks.discard(task_id)
        self._active_streams.discard(task_id)

# Global singleton instance of TaskManager
task_manager = TaskManager()
