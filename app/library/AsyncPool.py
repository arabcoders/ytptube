import asyncio
import logging
import uuid
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
        loop: asyncio.AbstractEventLoop | None = None,
        load_factor: int = 1,
        max_task_time: int | None = None,
        return_futures: bool = False,
        raise_on_join: bool = False,
    ):
        """
        This class will create `num_workers` asyncio tasks to work against a queue of
        `num_workers * load_factor` items of back-pressure (IOW we will block after such
        number of items of work is in the queue).  `worker_co` will be called
        against each item retrieved from the queue. If any exceptions are raised out of
        worker_co, self.exceptions will be set to True.

        Args:
            num_workers (int): number of async tasks which will pull from the internal queue
            worker_co (coroutine): async coroutine to call when an item is retrieved from the queue
            name (str): name of the worker pool (used for logging)
            logger (logging.Logger): logger to use
            loop (asyncio.AbstractEventLoop|None): asyncio loop to use
            load_factor (int): multiplier used for number of items in queue
            max_task_time (int|None): maximum time allowed for each task before a CancelledError is raised in the task.
            return_futures (bool): set to reture to return a future for each `push` (imposes CPU overhead)
            raise_on_join (bool): raise on join if any exceptions have occurred, default is False

        Returns:
            AsyncPool: instance of AsyncPool

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

    @property
    def exceptions(self):
        return self._exceptions

    async def _worker_loop(self, worker_id: str):
        """
        The main persistent worker loop that continuously processes jobs from the shared queue.

        Args:
            worker_id (str): the id of the worker processing this job.

        """
        while True:
            item = await self._queue.get()
            should_continue = await self._process_item(worker_id, item, from_queue=True)
            if not should_continue:
                break

    async def _process_item(self, worker_id: str, item: tuple | Terminator, from_queue: bool = True) -> bool:
        """
        Processes a single job item.

        Args:
            worker_id (str): the id of the worker processing this job.
            item (tuple|Terminator): the job item (tuple of (future, args, kwargs)) or a Terminator.
            from_queue (bool): indicates whether the job came from the shared queue; if True, task_done() is called.

        Returns:
            bool: False if the item is a Terminator (indicating termination), True otherwise.

        """
        future = None
        is_terminator = isinstance(item, Terminator)

        try:
            if is_terminator:
                return False

            future, args, kwargs = item

            self._status[worker_id] = {
                "started": self._time().isoformat(),
                "data": kwargs.get("entry", {"info": {}}).info.__dict__,
            }

            result = await asyncio.wait_for(self._worker_co(*args, **kwargs), timeout=self._max_task_time)

            if future:
                future.set_result(result)
        except (KeyboardInterrupt, MemoryError, SystemExit) as e:
            if future:
                future.set_exception(e)
            self._exceptions = True
            raise
        except Exception as e:
            self._exceptions = True
            if future:
                future.set_exception(e)
            else:
                self._logger.exception(f"Worker call failed. {e!s}")
        finally:
            self._status[worker_id] = None
            if not is_terminator and from_queue:
                self._queue.task_done()

        return True

    def has_open_workers(self) -> bool:
        """
        Check if there are open workers.

        Returns:
            bool: True if there are open workers, False otherwise.

        """
        return self.get_available_workers() > 0

    def get_available_workers(self) -> int:
        """
        Get the number of available workers.

        Returns:
            int: number of available workers.

        """
        return sum(1 for worker_status in self._status.values() if worker_status is None)

    def get_workers_status(self) -> dict[str, datetime | None]:
        """
        Get the status of all workers.

        Returns:
            dict: dictionary of worker status.

        """
        return self._status

    async def __aenter__(self):
        self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.join()

    async def push(self, *args, is_temp: bool = False, **kwargs) -> asyncio.Future:
        """
        Push work to the worker_co. If is_temp is True, a temporary worker is spawned

        Args:
            args: position arguments to be passed to `worker_co`
            is_temp (bool): flag to indicate if the job is temporary, default is False
            kwargs (dict): keyword arguments to be passed to `worker_co`

        Returns:
            asyncio.Future: future of result.

        """
        future = asyncio.futures.Future(loop=self._loop) if self._return_futures else None

        if is_temp:
            temp_worker_id = f"temp_worker_{uuid.uuid4()!s}"
            self._logger.info(f"Creating temporary worker '{temp_worker_id}'.")
            # Spawn a temporary worker that processes this one job.
            task = asyncio.ensure_future(
                self._process_item(temp_worker_id, (future, args, kwargs), from_queue=False), loop=self._loop
            )
            self._workers[temp_worker_id] = task

            # Attach a callback to clean up temporary worker entries when done.
            def cleanup_temp_worker(_):
                self._workers.pop(temp_worker_id, None)
                self._status.pop(temp_worker_id, None)
                self._logger.info(f"Temporary worker '{temp_worker_id}' has terminated.")

            task.add_done_callback(cleanup_temp_worker)

            return future

        await self._queue.put((future, args, kwargs))
        self._logger.debug(f"'{self._name}' pool has received a new job. {args} {kwargs}")
        return future

    def start(self):
        """
        Will start up worker pool and reset exception state
        """
        self._exceptions = False

        for worker_number in range(self._num_workers):
            worker_id = f"worker_{worker_number+1}"
            self._create_worker(worker_id)

    async def restart(self, worker_id: str, msg: str | None = None) -> bool:
        """
        Will restart the worker pool

        Args:
            worker_id (str): worker id to restart
            msg (str|None): message to send to the worker, default is None

        Returns:
            bool: True if worker was restarted.

        """
        if worker_id not in self._workers:
            self._logger.warning(f"Worker {worker_id} does not exist.")
            return False

        try:
            self._workers[worker_id].cancel(msg)
            await self._workers[worker_id]
        except asyncio.exceptions.CancelledError as e:
            self._logger.warning(f"Worker {worker_id} restarted. {e!s}")
            if worker_id in self._status:
                self._status.pop(worker_id)

            if worker_id in self._workers:
                self._workers.pop(worker_id)

            self._create_worker(worker_id)

        return True

    async def on_shutdown(self, _) -> None:
        """
        Will shutdown the worker pool
        """
        try:
            await asyncio.wait_for(asyncio.gather(*[self.stop(worker_id) for worker_id in self._workers]), timeout=10)
        except Exception:
            self._logger.error(f"Exception shutting down {self._name}")

    async def stop(self, worker_id: str, msg: str | None = None) -> bool:
        """
        Will stop the worker

        Args:
            worker_id (str): worker id to stop
            msg (str|None): message to send to the worker, default is None

        Returns:
            bool: True if worker was stopped.

        """
        if worker_id not in self._workers:
            self._logger.warning(f"Worker {worker_id} does not exist.")
            return False

        if self._workers[worker_id].cancel(msg):
            try:
                await self._workers[worker_id]
            except asyncio.exceptions.CancelledError as e:
                self._logger.warning(f"Worker {worker_id} stopped. {e!s}")
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
            msg = f"Exception occurred in {self._name} pool"
            raise Exception(msg)

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
