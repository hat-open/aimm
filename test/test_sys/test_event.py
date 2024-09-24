from hat import json
from hat import aio
from hat.drivers import tcp
import asyncio
import contextlib
import hat.event.eventer.client
import hat.event.common
import psutil
import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture
def conf_path(tmp_path):
    return tmp_path


@pytest.fixture
def event_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
async def event_server(event_port, conf_path):
    conf = {
        "type": "event",
        "log": {
            "disable_existing_loggers": False,
            "formatters": {"default": {}},
            "handlers": {
                "syslog": {
                    "class": "hat.syslog.handler.SysLogHandler",
                    "comm_type": "TCP",
                    "formatter": "default",
                    "host": "127.0.0.1",
                    "level": "INFO",
                    "port": 6514,
                    "queue_size": 10,
                }
            },
            "root": {
                "handlers": ["syslog"],
                "level": "INFO",
            },
            "version": 1,
        },
        "name": "event-server",
        "server_id": 0,
        "backend": {"module": "hat.event.backends.dummy"},
        "modules": [],
        "eventer_server": {"host": "127.0.0.1", "port": event_port},
        "synced_restart_engine": False,
    }
    event_conf_path = conf_path / "event.yaml"
    json.encode_file(conf, event_conf_path)
    proc = psutil.Popen(
        ["python", "-m", "hat.event.server", "--conf", str(event_conf_path)]
    )
    try:
        while not _listens_on(proc, event_port):
            await asyncio.sleep(0.1)
        yield proc
    finally:
        proc.kill()
        proc.wait()


def simple_conf(event_port):
    return {
        "log": {
            "version": 1,
            "formatters": {"default": {}},
            "handlers": {
                "syslog": {
                    "class": "hat.syslog.handler.SysLogHandler",
                    "host": "127.0.0.1",
                    "port": 6514,
                    "comm_type": "TCP",
                    "level": "INFO",
                    "formatter": "default",
                    "queue_size": 10,
                }
            },
            "root": {"level": "INFO", "handlers": ["syslog"]},
            "disable_existing_loggers": False,
        },
        "engine": {
            "sigterm_timeout": 5,
            "max_children": 5,
            "check_children_period": 3,
        },
        "backend": {
            "module": "aimm.server.backend.event",
            "model_prefix": ["aimm", "model"],
        },
        "control": [
            {
                "module": "aimm.server.control.event",
                "event_prefixes": {
                    "create_instance": ["create_instance"],
                    "add_instance": ["add_instance"],
                    "update_instance": ["update_instance"],
                    "fit": ["fit"],
                    "predict": ["predict"],
                    "cancel": ["cancel"],
                },
                "state_event_type": ["aimm", "state"],
                "action_state_event_type": ["aimm", "action_state"],
            }
        ],
        "plugins": {"names": ["test_sys.plugins.basic"]},
        "hat": {"eventer_server": {"host": "127.0.0.1", "port": event_port}},
        "name": "sys-test-event",
    }


@pytest.fixture
async def aimm_server_proc(event_port, event_server, conf_path):
    conf = simple_conf(event_port)
    aimm_conf_path = conf_path / "aimm.yaml"
    json.encode_file(conf, aimm_conf_path)
    proc = psutil.Popen(
        ["python", "-m", "aimm.server", "--conf", str(aimm_conf_path)]
    )
    await asyncio.sleep(1)
    yield proc
    proc.kill()
    proc.wait()


@pytest.fixture
def event_client_factory(event_port):
    @contextlib.asynccontextmanager
    async def factory(subscriptions):
        queue = aio.Queue()

        async def events_cb(_, events):
            queue.put_nowait(events)

        client = await hat.event.eventer.client.connect(
            tcp.Address(host="127.0.0.1", port=event_port),
            "sys-test-client",
            subscriptions=subscriptions,
            events_cb=events_cb,
        )
        yield client, queue
        await client.async_close()

    return factory


async def test_create_instance(aimm_server_proc, event_client_factory):
    model_type = "test_sys.plugins.basic.Model1"

    async with event_client_factory(
        [("aimm", "action_state"), ("aimm", "model", "*")]
    ) as (client, events_queue):
        args = ["a1", "a2"]
        kwargs = {"k1": "1", "k2": "2"}
        await client.register(
            [
                _register_event(
                    ("create_instance",),
                    {
                        "model_type": model_type,
                        "args": args,
                        "kwargs": kwargs,
                        "request_id": 1,
                    },
                )
            ],
            with_response=True,
        )

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "action_state")
        assert event.source_timestamp is None
        payload = event.payload.data
        assert set(payload.keys()) == {"request_id", "status", "result"}
        assert payload["status"] == "IN_PROGRESS"
        assert payload["result"] is None

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "model", "1")
        assert event.source_timestamp is None
        payload = event.payload.data
        assert set(payload.keys()) == {"type", "instance"}
        assert payload["type"] == model_type

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "action_state")
        assert event.source_timestamp is None
        payload = event.payload.data
        assert set(payload.keys()) == {"request_id", "status", "result"}
        assert payload["status"] == "DONE"
        assert payload["result"] == 1


async def _create_instance(client, model_type, events_queue):
    args = ["a1", "a2"]
    kwargs = {"k1": "1", "k2": "2"}
    await client.register(
        [
            _register_event(
                ("create_instance",),
                {
                    "model_type": model_type,
                    "args": args,
                    "kwargs": kwargs,
                    "request_id": 1,
                },
            )
        ],
        with_response=True,
    )

    events = await events_queue.get()
    event = events[0]
    assert event.payload.data["status"] == "IN_PROGRESS"

    events = await events_queue.get()
    event = events[0]
    assert event.type == ("aimm", "model", "1")

    events = await events_queue.get()
    event = events[0]
    payload = event.payload.data
    assert payload["status"] == "DONE"
    model_id = payload["result"]

    return model_id


async def test_fit(aimm_server_proc, event_client_factory):
    model_type = "test_sys.plugins.basic.Model1"

    async with event_client_factory(
        [("aimm", "action_state"), ("aimm", "model", "*")]
    ) as (client, events_queue):
        model_id = await _create_instance(client, model_type, events_queue)

        args = ["a3", "a4"]
        kwargs = {"k3": "3", "k4": "4"}
        await client.register(
            [
                _register_event(
                    ("fit", str(model_id)),
                    {"args": args, "kwargs": kwargs, "request_id": 1},
                )
            ],
            with_response=True,
        )

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "action_state")
        assert event.source_timestamp is None
        payload = event.payload.data
        assert set(payload.keys()) == {"request_id", "status", "result"}
        assert payload["status"] == "IN_PROGRESS"
        assert payload["result"] is None

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "model", str(model_id))
        assert event.source_timestamp is None
        assert event.payload.data["type"] == model_type
        assert event.payload.data["instance"] is not None

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "action_state")
        assert event.source_timestamp is None
        payload = event.payload.data
        assert set(payload.keys()) == {"request_id", "status", "result"}
        assert payload["status"] == "DONE"
        assert payload["result"] is None


async def test_predict(aimm_server_proc, event_client_factory):
    model_type = "test_sys.plugins.basic.Model1"

    async with event_client_factory(
        [("aimm", "action_state"), ("aimm", "model", "*")]
    ) as (client, events_queue):
        model_id = await _create_instance(client, model_type, events_queue)

        args = ["a3", "a4"]
        kwargs = {"k3": "3", "k4": "4"}
        await client.register(
            [
                _register_event(
                    ("predict", str(model_id)),
                    {"args": args, "kwargs": kwargs, "request_id": 1},
                )
            ],
            with_response=True,
        )

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "action_state")
        assert event.source_timestamp is None
        payload = event.payload.data
        assert set(payload.keys()) == {"request_id", "status", "result"}
        assert payload["status"] == "IN_PROGRESS"
        assert payload["result"] is None

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "model", str(model_id))
        assert event.source_timestamp is None
        assert event.payload.data["type"] == model_type
        assert event.payload.data["instance"] is not None

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "action_state")
        assert event.source_timestamp is None
        payload = event.payload.data
        assert set(payload.keys()) == {"request_id", "status", "result"}
        assert payload["status"] == "DONE"
        assert payload["result"] == [args, kwargs]


async def test_cancel(aimm_server_proc, event_client_factory):
    model_type = "test_sys.plugins.basic.Model1"

    async with event_client_factory(
        [("aimm", "action_state"), ("aimm", "model", "*")]
    ) as (client, events_queue):
        model_id = await _create_instance(client, model_type, events_queue)
        await client.register(
            [
                _register_event(
                    ("predict", str(model_id)),
                    {
                        "args": [10],
                        "kwargs": {},
                        "request_id": "1",
                    },  # sleep 10 seconds
                )
            ],
            with_response=True,
        )

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "action_state")
        assert event.source_timestamp is None
        payload = event.payload.data
        assert set(payload.keys()) == {"request_id", "status", "result"}
        assert payload["status"] == "IN_PROGRESS"
        assert payload["result"] is None

        event_queue = aio.Queue()

        async def wait_events():
            event_queue.put_nowait(await events_queue.get())

        async with aio.Group() as group:
            group.spawn(wait_events)
            await asyncio.sleep(2)
            assert event_queue.empty()

        await client.register(
            [_register_event(("cancel",), "1")], with_response=True
        )

        events = await events_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.type == ("aimm", "action_state")
        assert event.source_timestamp is None
        payload = event.payload.data
        assert set(payload.keys()) == {"request_id", "status", "result"}
        assert payload["status"] == "CANCELLED"
        assert payload["result"] is None


def _listens_on(proc, port):
    return port in (
        conn.laddr.port
        for conn in proc.net_connections()
        if conn.status == "LISTEN"
    )


def _register_event(event_type, payload):
    return hat.event.common.RegisterEvent(
        type=event_type,
        source_timestamp=None,
        payload=hat.event.common.EventPayloadJson(payload),
    )
