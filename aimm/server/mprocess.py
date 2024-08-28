"""Provides an interface to managed process calls. The main component is a
:class:`ProcessManager` object, that is used to create :class:`ProcessHandler`
objects, wrappers for the process calls."""

from hat import aio
from typing import Any, Callable, NamedTuple, Optional
import asyncio
import contextlib
import enum
import logging
import multiprocessing
import psutil
import signal


mlog = logging.getLogger(__name__)

StateCallback = Callable[[Any], None]

mp_context = multiprocessing.get_context("fork")


class ProcessManager(aio.Resource):
    """Class used to create :class:`ProcessHandler` objects and limit the
    amount of concurrently active child processes.

    Args:
        max_children: maximum number of child processes that may be created
        async_group: async group
        check_children_period: number of seconds waited before checking if a
            child process may be created and notifying pending handlers
        sigterm_timeout: number of seconds waited before sending SIGKILL if a
            child process does not terminate after SIGTERM"""

    def __init__(
        self,
        max_children: int,
        async_group: aio.Group,
        check_children_period: float,
        sigterm_timeout: float,
    ):
        self._max_children = max_children
        self._async_group = async_group
        self._check_children_period = check_children_period
        self._sigterm_timeout = sigterm_timeout

        self._condition = asyncio.Condition()

        self._async_group.spawn(self._condition_loop)

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    def create_handler(self, state_cb: StateCallback) -> "ProcessHandler":
        """Creates a ProcessHandler

        Args:
            state_cb (Callable[List[Any], None]): state callback for changes
                in the process call

        Returns:
            ProcessHandler"""
        return ProcessHandler(
            self._async_group.create_subgroup(),
            self._sigterm_timeout,
            state_cb,
            self._condition,
        )

    async def _condition_loop(self):
        condition = self._condition
        process = psutil.Process()
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                async with condition:
                    available_processes = self._max_children - len(
                        process.children()
                    )
                    if available_processes > 0:
                        condition.notify(available_processes)
                await asyncio.sleep(self._check_children_period)


class ProcessHandler(aio.Resource):
    """Handler for calls in separate processes. Created through
    :meth:`ProcessManager.create`.

    Args:
        async_group (hat.aio.Group): async group
        sigterm_timeout (float): time waited until process handles SIGTERM
            before sending SIGKILL during forced shutdown
        state_cb (Optional[Callable[Any]]): state change cb
        condition (asyncio.Condition): condition that notifies when a new
            process may be created
    """

    def __init__(
        self,
        async_group: aio.Group,
        sigterm_timeout: float,
        state_cb: StateCallback,
        condition: asyncio.Condition,
    ):
        self._async_group = async_group
        self._sigterm_timeout = sigterm_timeout
        self._state_cb = state_cb
        self._condition = condition

        self._result_pipe = mp_context.Pipe(False)
        self._state_pipe = mp_context.Pipe(False)

        self._process = None
        self._executor = aio.create_executor()

        self._async_group.spawn(self._state_loop)
        self._async_group.spawn(aio.call_on_cancel, self._cleanup)

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    def proc_notify_state_change(self, state: Any):
        """To be passed to and ran in the separate process call. Notifies the
        handler of state change, new state is passed to ``state_cb`` received
        in the constructor.

        Args:
            state: call state, needs to be pickleable

        """
        self._state_pipe[1].send(state)

    async def run(self, fn: Callable, *args: Any, **kwargs: Any):
        """Requests the start of function execution in the separate process.

        Args:
            fn: function that will be called
            *args: positional arguments, need to be pickleable
            **kwargs: keyword arguments, need to be pickleable

        """
        await self._condition.acquire()
        try:
            await self._condition.wait()
            self._process = mp_context.Process(
                target=_proc_run_fn,
                args=(self._result_pipe, fn, *args),
                kwargs=kwargs,
            )
            self._process.start()

            async def wait_result():
                try:
                    result = await self._executor(
                        _ext_closeable_recv, self._result_pipe
                    )
                    if result.success:
                        return result.result
                    else:
                        raise result.exception
                except _ProcessTerminatedException:
                    raise Exception("process terminated")

            return await aio.uncancellable(wait_result())
        finally:
            self._condition.release()
            self._async_group.close()

    async def _state_loop(self):
        with contextlib.suppress(asyncio.CancelledError, ValueError):
            while True:
                state = await self._executor(
                    _ext_closeable_recv, self._state_pipe
                )
                if self._state_cb:
                    self._state_cb(state)

    async def _cleanup(self):
        if self._process is not None:
            await self._executor(
                _ext_end_process, self._process, self._sigterm_timeout
            )
        await self._executor(_ext_close_pipe, self._result_pipe)
        await self._executor(_ext_close_pipe, self._state_pipe)


class _Result(NamedTuple):
    success: bool
    result: Optional[Any] = None
    exception: Optional[Exception] = None


class _ProcessTerminatedException(Exception):
    pass


def _plugin_sigterm_handler(frame, signum):
    raise Exception("process terminated")


@contextlib.contextmanager
def _sigterm_override():
    try:
        signal.signal(signal.SIGTERM, _plugin_sigterm_handler)
        yield
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)


def _proc_run_fn(pipe, fn, *args, **kwargs):
    try:
        with _sigterm_override():
            result = _Result(success=True, result=fn(*args, **kwargs))
    except Exception as e:
        result = _Result(success=False, exception=e)
    pipe[1].send(result)


def _ext_end_process(process, sigterm_timeout):
    if process.is_alive():
        process.terminate()
        process.join(sigterm_timeout)
    if process.is_alive():
        process.kill()
    process.join()
    process.close()


class _PipeSentinel(enum.Enum):
    CLOSE = enum.auto


def _ext_close_pipe(pipe):
    _, send_conn = pipe
    send_conn.send(_PipeSentinel.CLOSE)
    send_conn.close()


def _ext_closeable_recv(pipe):
    recv_conn, _ = pipe
    value = recv_conn.recv()
    if value == _PipeSentinel.CLOSE:
        raise _ProcessTerminatedException("pipe closed")
    return value
