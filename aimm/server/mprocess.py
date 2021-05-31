"""Provides an interface to managed process calls. The main component is a
:class:`ProcessManager` object, that is used to create :class:`ProcessHandler`
objects, wrappers for the process calls."""

import asyncio
import contextlib
import enum
from hat import aio
import logging
import multiprocessing
import psutil
import signal
from typing import Callable, Any


mlog = logging.getLogger(__name__)

StateCallback = Callable[[Any], None]


class ProcessManager(aio.Resource):

    """Class used to create :class:`ProcessHandler` objects and limit the
    amount of concurrently active child processes.

    Args:
        max_children: maximum number of child processes that may be created
        group: asyncio group
        check_children_period: number of seconds waited before checking if a
            child process may be created and notifying pending handlers
        sigterm_timeout: number of seconds waited before sending SIGKILL if a
            child process does not terminate after SIGTERM"""

    def __init__(self,
                 max_children: int,
                 group: aio.Group,
                 check_children_period: float,
                 sigterm_timeout: float):
        self._max_children = max_children
        self._group = group
        self._check_children_period = check_children_period
        self._sigterm_timeout = sigterm_timeout

        self._condition = asyncio.Condition()

        self._group.spawn(self._condition_loop)

    @property
    def async_group(self) -> aio.Group:
        return self._group

    def create_handler(self, state_cb: StateCallback) -> 'ProcessHandler':
        """Creates a ProcessHandler

        Args:
            state_cb (Callable[List[Any], None]): state callback for changes
                in the process call

        Returns:
            ProcessHandler"""
        return ProcessHandler(self._group.create_subgroup(),
                              self._sigterm_timeout, state_cb,
                              self._condition)

    async def _condition_loop(self):
        cond = self._condition
        process = psutil.Process()
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                async with cond:
                    available_processes = (self._max_children
                                           - len(process.children()))
                    if available_processes > 0:
                        cond.notify(available_processes)
                await asyncio.sleep(self._check_children_period)


class ProcessHandler(aio.Resource):
    """Handler for calls in separate processes. Created through
    :meth:`ProcessManager.create`.

    Args:
        group (hat.aio.Group): async group
        sigterm_timeout (float): time waited until process handles SIGTERM
            before sending SIGKILL during forced shutdown
        state_cb (Optional[Callable[Any]]): state change cb
        cond (asyncio.Condition): condition that notifies when a new process
            may be created
    """

    def __init__(self,
                 group: aio.Group,
                 sigterm_timeout: float,
                 state_cb: StateCallback,
                 cond: asyncio.Condition):
        self._group = group
        self._sigterm_timeout = sigterm_timeout
        self._state_cb = state_cb
        self._cond = cond

        self._result_pipe = multiprocessing.Pipe(False)
        self._state_pipe = multiprocessing.Pipe(False)

        self._process = None
        self._executor = aio.create_executor()
        self._result_future = asyncio.Future()

        self._group.spawn(self._state_loop)
        self._group.spawn(aio.call_on_cancel, self._cleanup)

    @property
    def async_group(self) -> aio.Group:
        return self._group

    @property
    def result(self) -> asyncio.Future:
        """asyncio.Future: contains return value of the call as result"""
        return self._result_future

    def proc_notify_state_change(self, state: Any):
        """To be passed to and ran in the separate process call. Notifies the
        handler of state change, new state is passed to ``state_cb`` received
        in the constructor.

        Args:
            state: call state, needs to be pickleable

        """
        self._state_pipe[1].send(state)

    def run(self, fn: Callable, *args: Any, **kwargs: Any):
        """Requests the start of function execution in the separate process.

        Args:
            fn: function that will be called
            *args: positional arguments, need to be pickleable
            **kwargs: keyword arguments, need to be pickleable

        """
        self._group.spawn(self._run, self._cond, fn, *args, **kwargs)

    async def _run(self, cond, fn, *args, **kwargs):
        await cond.acquire()
        try:
            await cond.wait()
            self._process = multiprocessing.Process(
                target=_proc_run_fn,
                args=(self._result_pipe, fn, *args),
                kwargs=kwargs)
            self._process.start()

            async def wait_result():
                try:
                    result = await self._executor(_ext_closeable_recv,
                                                  self._result_pipe)
                    if result['success']:
                        self._result_future.set_result(result['result'])
                    else:
                        self._result_future.set_exception(result['exception'])
                except ValueError:
                    self._result_future.set_exception(
                        Exception('process killed'))

            await aio.uncancellable(wait_result())
        finally:
            cond.release()
            self._group.close()

    async def _state_loop(self):
        with contextlib.suppress(asyncio.CancelledError, ValueError):
            while True:
                state = await self._executor(_ext_closeable_recv,
                                             self._state_pipe)
                if self._state_cb:
                    self._state_cb(state)

    async def _cleanup(self):
        if self._process is not None:
            await self._executor(_ext_end_process, self._process,
                                 self._sigterm_timeout)
        await self._executor(_ext_close_pipe, self._result_pipe)
        await self._executor(_ext_close_pipe, self._state_pipe)


def _plugin_sigterm_handler(frame, signum):
    raise Exception('process terminated')


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
            result = {'success': True,
                      'result': fn(*args, **kwargs)}
    except Exception as e:
        result = {'success': False, 'exception': e}
    pipe[1].send(result)


def _ext_end_process(process, sigterm_timeout):
    if process.is_alive():
        process.terminate()
        process.join(sigterm_timeout)
    if process.is_alive():
        process.kill()
    process.join()
    process.close()


class _PipeSentinels(enum.Enum):
    CLOSE = enum.auto


def _ext_close_pipe(pipe):
    _, send_conn = pipe
    send_conn.send(_PipeSentinels.CLOSE)
    send_conn.close()


def _ext_closeable_recv(pipe):
    recv_conn, _ = pipe
    value = recv_conn.recv()
    if value == _PipeSentinels.CLOSE:
        raise ValueError('pipe closed')
    return value