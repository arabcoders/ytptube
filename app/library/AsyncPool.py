import asyncio
import logging
from datetime import UTC, datetime


class Terminator:
    pass


class AsyncPool:
    def __init__(
        self,
        num_workers: int,
        worker_co,
        name: str,
        logger: logging.Logger,
        loop: asyncio.AbstractEventLoop|None = None,
        load_factor: int = 1,
        max_task_time: int|None = None,
        return_futures: bool = False,
        raise_on_join: bool = False,
    ):
        """
        This class will create `num_workers` asyncio tasks to work against a queue of
        `num_workers * load_factor` items of back-pressure (IOW we will block after such
        number of items of work is in the queue).  `worker_co` will be called
        against each item retrieved from the queue. If any exceptions are raised out of
        worker_co, self.exceptions will be set to True.

        :param loop: asyncio loop to use
        :param num_workers: number of async tasks which will pull from the internal queue
        :param name: name of the worker pool (used for logging)
        :param logger: logger to use
        :param worker_co: async coroutine to call when an item is retrieved from the queue
        :param load_factor: multiplier used for number of items in queue
        :param max_task_time: maximum time allowed for each task before a CancelledError is raised in the task.
            Set to None for no limit.
        :param return_futures: set to reture to return a future for each `push` (imposes CPU overhead)
        :param raise_on_join: raise on join if any exceptions have occurred, default is False

        :return: instance of AsyncWorkerPool
        """
        self._loop = loop if loop else asyncio.get_event_loop()
        self._num_workers = num_workers
        self._logger = logger if logger else logging.getLogger(__name__)
        self._queue = asyncio.Queue(num_workers * load_factor)
        self._workers: dict[str, asyncio.Future] = {}
        self._exceptions = False
        self._max_task_time = max_task_time
        self._return_futures = return_futures
        self._raise_on_join = raise_on_join
        self._name = name
        self._worker_co = worker_co
        self._status: dict[str, dict | None] = {}

    async def _worker_loop(self, worker_id: str):
        while True:
            got_obj = False
            future = None
            try:
                item = await self._queue.get()
                got_obj = True

                if item.__class__ is Terminator:
                    break

                future, args, kwargs = item

                self._status[worker_id] = {
                    "started": self._time().isoformat(),
                    "data": kwargs.get("entry", {"info": {}}).info.__dict__,
                }

                # the wait_for will cancel the task (task sees CancelledError) and raises a TimeoutError from here
                # so be wary of catching TimeoutErrors in this loop
                result = await asyncio.wait_for(self._worker_co(*args, **kwargs), timeout=self._max_task_time)

                if future:
                    future.set_result(result)
            except (KeyboardInterrupt, MemoryError, SystemExit) as e:
                if future:
                    future.set_exception(e)
                self._exceptions = True
                raise
            except BaseException as e:
                if isinstance(e, asyncio.exceptions.CancelledError):
                    raise e

                self._exceptions = True

                if future:
                    # don't log the failure when the client is receiving the future
                    future.set_exception(e)
                else:
                    self._logger.exception(f"Worker call failed. {str(e)}")
            finally:
                self._status[worker_id] = None

                if got_obj:
                    self._queue.task_done()

    @property
    def exceptions(self):
        return self._exceptions

    def has_open_workers(self) -> bool:
        """
        :return: True if there are open workers.
        """
        return self.get_available_workers() > 0

    def get_available_workers(self) -> int:
        """
        :return: number of available workers.
        """
        return sum(1 for worker_status in self._status.values() if worker_status is None)

    def get_workers_status(self) -> dict[str, datetime | None]:
        """
        :return: dictionary of worker status.
        """
        return self._status

    async def __aenter__(self):
        self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.join()

    async def push(self, *args, **kwargs) -> asyncio.Future:
        """
        Method to push work to `worker_co` passed initially to `__init__`.

        :param args: position arguments to be passed to `worker_co`
        :param kwargs: keyword arguments to be passed to `worker_co`

        :return: future of result.
        """
        future = asyncio.futures.Future(loop=self._loop) if self._return_futures else None
        await self._queue.put((future, args, kwargs))

        self._logger.debug(f"'{self._name}' pool has received a new job. {args} {kwargs}")

        return future

    def start(self):
        """Will start up worker pool and reset exception state"""
        self._exceptions = False

        for worker_number in range(self._num_workers):
            worker_id = f"worker_{worker_number+1}"
            self._create_worker(worker_id)

    async def restart(self, worker_id: str, msg: str = None) -> bool:
        """Will restart the worker pool"""
        if worker_id not in self._workers:
            self._logger.warning(f"Worker {worker_id} does not exist.")
            return False

        try:
            self._workers[worker_id].cancel(msg)
            await self._workers[worker_id]
        except asyncio.exceptions.CancelledError as e:
            self._logger.warning(f"Worker {worker_id} restarted. {str(e)}")
            if worker_id in self._status:
                self._status.pop(worker_id)

            if worker_id in self._workers:
                self._workers.pop(worker_id)

            self._create_worker(worker_id)

        return True

    async def stop(self, worker_id: str, msg: str = None) -> bool:
        """Will stop the worker"""
        if worker_id not in self._workers:
            self._logger.warning(f"Worker {worker_id} does not exist.")
            return False

        if self._workers[worker_id].cancel(msg):
            try:
                await self._workers[worker_id]
            except asyncio.exceptions.CancelledError as e:
                self._logger.warning(f"Worker {worker_id} stopped. {str(e)}")
                if worker_id in self._status:
                    self._status.pop(worker_id)

                if worker_id in self._workers:
                    self._workers.pop(worker_id)

        return True

    async def join(self) -> None:
        # no-op if workers aren't running
        if len(self._workers) < 1:
            return

        self._logger.info(f"Joining {self._name}")

        # The Terminators will kick each worker from being blocked against the _queue.get() and allow
        # each one to exit.
        for _ in range(self._num_workers):
            await self._queue.put(Terminator())

        try:
            await asyncio.gather(*list(self._workers))
            self._workers = {}
        except:
            self._logger.exception(f"Exception joining {self._name}")
            raise
        finally:
            self._logger.info(f"Completed {self._name}")

        if self._exceptions and self._raise_on_join:
            raise Exception(f"Exception occurred in {self._name} pool")

    def _create_worker(self, worker_id: str) -> asyncio.Future:
        if worker_id in self._workers:
            self._logger.debug(f"Worker {worker_id} already exists.")
            return self._workers[worker_id]

        self._status[worker_id] = None
        self._workers[worker_id] = asyncio.ensure_future(
            coro_or_future=self._worker_loop(worker_id=worker_id), loop=self._loop
        )

        self._logger.debug(f"Created {worker_id}")

        return self._workers[worker_id]

    def _time(self) -> datetime:
        return datetime.now(tz=UTC)
