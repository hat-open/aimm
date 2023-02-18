from hat import aio
from pytest_cov.embed import cleanup_on_signal
import asyncio
import contextlib
import pytest
import signal
import time

from aimm.server import mprocess


@pytest.fixture
def disable_sigterm_handler(monkeypatch):
    default = mprocess._sigterm_override

    @contextlib.contextmanager
    def handler_patch():
        cleanup_on_signal(signal.SIGTERM)
        with default():
            yield

    with monkeypatch.context() as ctx:
        ctx.setattr(mprocess, "_sigterm_override", handler_patch)
        yield


@pytest.mark.timeout(2)
@pytest.mark.parametrize("action_count", [1, 2, 10])
async def test_process_regular(action_count, disable_sigterm_handler):
    def fn(*args, **kwargs):
        return args, kwargs

    args = ("arg1", "arg2")
    kwargs = {"k1": "v1", "k2": "v2"}

    pa_pool = mprocess.ProcessManager(1, aio.Group(), 0.1, 2)
    async with aio.Group() as group:
        tasks = []
        for _ in range(action_count):
            process_action = pa_pool.create_handler(lambda: None)
            tasks.append(group.spawn(process_action.run, fn, *args, **kwargs))
        await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    assert [t.result() for t in tasks] == [(args, kwargs)] * action_count
    await process_action.wait_closed()

    await pa_pool.async_close()


@pytest.mark.timeout(2)
async def test_process_exception(disable_sigterm_handler):
    exception_text = "test exception"

    def fn():
        raise Exception(exception_text)

    pa_pool = mprocess.ProcessManager(1, aio.Group(), 0.1, 2)
    process_action = pa_pool.create_handler(lambda: None)

    with pytest.raises(Exception, match=exception_text):
        await process_action.run(fn)
    await process_action.wait_closed()

    await pa_pool.async_close()


@pytest.mark.timeout(2)
async def test_process_sigterm(disable_sigterm_handler):
    def fn():
        time.sleep(10)

    queue = aio.Queue()

    def state_cb(state):
        queue.put_nowait(state)

    pa_pool = mprocess.ProcessManager(1, aio.Group(), 0.1, 5)
    process_action = pa_pool.create_handler(lambda: None)
    async with aio.Group() as group:

        async def _run():
            with pytest.raises(Exception, match="process terminated"):
                await process_action.run(fn)

        task = group.spawn(_run)
        await asyncio.sleep(0.2)
        await process_action.async_close()
        await task
        assert not task.exception()

    await pa_pool.async_close()


@pytest.mark.timeout(2)
async def test_process_sigkill():
    def fn():
        try:
            time.sleep(10)
        except Exception:
            time.sleep(10)

    queue = aio.Queue()

    def state_cb(state):
        queue.put_nowait(state)

    pa_pool = mprocess.ProcessManager(1, aio.Group(), 0.1, 0.2)
    process_action = pa_pool.create_handler(lambda: None)
    async with aio.Group() as group:

        async def _run():
            with pytest.raises(Exception, match="process terminated"):
                await process_action.run(fn)

        task = group.spawn(_run)
        await asyncio.sleep(0.2)
        await process_action.async_close()
        await task
        assert not task.exception()

    await pa_pool.async_close()
