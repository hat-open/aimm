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
def monitor_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
async def monitor_server(monitor_port, unused_tcp_port_factory, conf_path):
    master_port = unused_tcp_port_factory()
    ui_port = unused_tcp_port_factory()
    conf = {
        "type": "monitor",
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
        "default_algorithm": "BLESS_ALL",
        "group_algorithms": {},
        "server": {
            "host": "127.0.0.1",
            "port": monitor_port,
            "default_rank": 1,
        },
        "master": {"host": "127.0.0.1", "port": master_port},
        "slave": {
            "parents": [],
            "connect_timeout": 5,
            "connect_retry_count": 5,
            "connect_retry_delay": 5,
        },
        "ui": {"host": "127.0.0.1", "port": ui_port},
    }
    monitor_conf_path = conf_path / "monitor.yaml"
    json.encode_file(conf, monitor_conf_path)
    proc = psutil.Popen(
        [
            "python",
            "-m",
            "hat.monitor.server",
            "--conf",
            str(monitor_conf_path),
        ]
    )
    try:
        while not _listens_on(proc, monitor_port):
            await asyncio.sleep(0.1)
        yield proc
    finally:
        proc.kill()
        proc.wait()


@pytest.fixture
def event_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def event_server_factory(event_port, conf_path):
    @contextlib.asynccontextmanager
    async def factory(monitor_port=None):
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
        if monitor_port:
            conf["monitor_component"] = {
                "group": "event",
                "host": "127.0.0.1",
                "port": monitor_port,
            }
        event_conf_path = conf_path / "event.yaml"
        json.encode_file(conf, event_conf_path)
        proc = psutil.Popen(
            [
                "python",
                "-m",
                "hat.event.server",
                "--conf",
                str(event_conf_path),
            ]
        )
        try:
            while not _listens_on(proc, event_port):
                await asyncio.sleep(0.1)
            yield proc
        finally:
            proc.kill()
            proc.wait()

    return factory


def aimm_conf(hat_conf):
    conf = {
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
            "module": "aimm.server.backend.dummy",
        },
        "control": [],
        "plugins": {"names": ["test_sys.plugins.basic"]},
        "name": "sys-test-event",
    }
    if hat_conf is not None:
        conf["hat"] = hat_conf
    return conf


@pytest.fixture
def aimm_server_factory(conf_path):
    @contextlib.asynccontextmanager
    async def factory(hat_conf):
        conf = aimm_conf(hat_conf)
        aimm_conf_path = conf_path / "aimm.yaml"
        json.encode_file(conf, aimm_conf_path)
        proc = psutil.Popen(
            ["python", "-m", "aimm.server", "--conf", str(aimm_conf_path)]
        )
        await asyncio.sleep(1)
        yield proc
        proc.kill()
        proc.wait()

    return factory


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


async def test_single(aimm_server_factory):
    async with aimm_server_factory(None) as aimm_proc:
        assert aimm_proc.is_running()


async def test_monitor_only(aimm_server_factory, monitor_port, monitor_server):
    async with aimm_server_factory(
        {
            "monitor_component": {
                "host": "127.0.0.1",
                "port": monitor_port,
                "group": "aimm",
            }
        }
    ) as aimm_proc:
        assert aimm_proc.is_running()
        assert _connected_to(aimm_proc, monitor_port)


async def test_eventer_only(
    aimm_server_factory, event_port, event_server_factory
):
    async with event_server_factory():
        async with aimm_server_factory(
            {
                "eventer_server": {
                    "host": "127.0.0.1",
                    "port": event_port,
                }
            }
        ) as aimm_proc:
            assert aimm_proc.is_running()
            assert _connected_to(aimm_proc, event_port)


async def test_complete_hat(
    aimm_server_factory,
    event_port,
    event_server_factory,
    monitor_port,
    monitor_server,
):
    async with event_server_factory(monitor_port):
        async with aimm_server_factory(
            {
                "monitor_component": {
                    "host": "127.0.0.1",
                    "port": monitor_port,
                    "group": "aimm",
                    "event_server_group": "event",
                }
            }
        ) as aimm_proc:
            assert aimm_proc.is_running()
            assert _connected_to(aimm_proc, monitor_port)
            assert _connected_to(aimm_proc, event_port)


def _listens_on(proc, port):
    return port in (
        conn.laddr.port
        for conn in proc.net_connections()
        if conn.status == "LISTEN"
    )


def _connected_to(proc, port):
    return port in (
        conn.raddr.port
        for conn in proc.net_connections()
        if conn.status == "ESTABLISHED"
    )
