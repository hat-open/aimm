from functools import partial
from hat import aio
from hat import json
from pathlib import Path
import appdirs
import argparse
import asyncio
import contextlib
import importlib
import hat.monitor.client
import hat.event.eventer_client
import hat.event.common
import logging.config
import sys

from aimm import plugins
from aimm.server import common
import aimm.server.backend
import aimm.server.control
import aimm.server.engine


mlog = logging.getLogger("aimm.server.main")
default_conf_path = Path(appdirs.user_data_dir("aimm")) / "server.yaml"


def main():
    aio.init_asyncio()

    args = _create_parser().parse_args()
    conf = json.decode_file(args.conf)
    common.json_schema_repo.validate("aimm://server/main.yaml#", conf)

    logging.config.dictConfig(conf["log"])
    plugins.initialize(conf["plugins"])
    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf))


async def async_main(conf):
    async_group = aio.Group()
    hat_conf = conf.get("hat") or {}
    if "monitor" in hat_conf:
        monitor = await hat.monitor.client.connect(hat_conf["monitor"])
        _bind_resource(async_group, monitor)

        component = hat.monitor.client.Component(
            monitor, run_monitor_component, conf, monitor
        )
        component.set_ready(True)
        _bind_resource(async_group, component)

        try:
            await async_group.wait_closing()
        finally:
            await aio.uncancellable(monitor.async_close())
    elif "event_server_address" in hat_conf:
        client = await hat.event.eventer_client.connect(
            hat_conf["event_server_address"], list(_get_subscriptions(conf))
        )
        _bind_resource(async_group, client)
        await async_group.spawn(run, conf, client)
    else:
        mlog.debug("running without hat compatibility")
        await run(conf)


async def run_monitor_component(_, conf, monitor):
    if "event_server_group" not in conf["hat"]:
        mlog.info("running without hat event compatibility")
        return await run(conf)
    run_conf = partial(run, conf)
    return await hat.event.eventer_client.run_eventer_client(
        monitor_client=monitor,
        server_group=conf["hat"]["event_server_group"],
        run_cb=run_conf,
        subscriptions=list(_get_subscriptions(conf)),
    )


async def run(conf, client=None):
    group = aio.Group()

    try:
        proxies = []

        backend, proxy = await _create_backend(conf["backend"], client)
        _bind_resource(group, backend)
        if proxy:
            proxies.append(proxy)

        engine = await aimm.server.engine.create(
            conf["engine"], backend, group.create_subgroup()
        )
        _bind_resource(group, engine)

        controls = []
        for control_conf in conf["control"]:
            control, proxy = await _create_control(
                control_conf, engine, client
            )
            _bind_resource(group, control)
            controls.append(control)
            if proxy:
                proxies.append(proxy)

        if proxies:
            group.spawn(_recv_loop, proxies, client)

        await group.wait_closing()
    finally:
        await aio.uncancellable(group.async_close())


def _get_subscriptions(conf):
    backend_module = importlib.import_module(conf["backend"]["module"])
    if hasattr(backend_module, "create_subscription"):
        subscription = backend_module.create_subscription(conf["backend"])
        yield from subscription.get_query_types()
    for control in conf["control"]:
        control_module = importlib.import_module(control["module"])
        if hasattr(control_module, "create_subscription"):
            subscription = control_module.create_subscription(control)
            yield from subscription.get_query_types()


async def _create_backend(conf, client):
    module = importlib.import_module(conf["module"])
    proxy = None
    if client and hasattr(module, "create_subscription"):
        proxy = common.ProxyClient(client, module.create_subscription(conf))
    return await module.create(conf, proxy), proxy


async def _create_control(conf, engine, client):
    module = importlib.import_module(conf["module"])
    proxy = None
    if client and hasattr(module, "create_subscription"):
        proxy = common.ProxyClient(client, module.create_subscription(conf))
    return await module.create(conf, engine, proxy), proxy


async def _recv_loop(proxies, client):
    while True:
        events = await client.receive()
        for proxy in proxies:
            proxy_events = [
                e for e in events if proxy.subscription.matches(e.event_type)
            ]
            if proxy_events:
                proxy.notify(proxy_events)


def _create_parser():
    parser = argparse.ArgumentParser(
        prog="aimm-server", description="Run AIMM server"
    )
    parser.add_argument(
        "--conf",
        metavar="path",
        dest="conf",
        default=default_conf_path,
        type=Path,
        help="configuration defined by aimm://server/main.yaml# "
        "(default $XDG_CONFIG_HOME/aimm/server.yaml)",
    )
    return parser


def _bind_resource(async_group, resource):
    async_group.spawn(aio.call_on_cancel, resource.async_close)
    async_group.spawn(
        aio.call_on_done, resource.wait_closing(), async_group.close
    )


if __name__ == "__main__":
    sys.exit(main())
