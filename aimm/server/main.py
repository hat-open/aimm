from functools import partial
from hat import aio
from hat import json
from hat.drivers import tcp
from pathlib import Path
from urllib.parse import urlparse
import appdirs
import argparse
import asyncio
import contextlib
import importlib
import hat.monitor.component
import hat.event.component
import hat.event.eventer.client
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
    hat_conf = conf.get("hat") or {}
    subscriptions = list(_get_subscriptions(conf))
    if monitor_conf := hat_conf.get("monitor"):
        runner = partial(run, conf)
        if event_server_group := hat_conf.get("event_server_group"):
            component = await hat.event.component.connect(
                _parse_tcp(monitor_conf["monitor_address"]),
                monitor_conf["name"],
                monitor_conf["group"],
                event_server_group,
                runner,
                eventer_kwargs={"subscriptions": subscriptions},
            )
        else:
            mlog.info("running without hat event compatibility")
            component = await hat.monitor.component.connect(
                _parse_tcp(monitor_conf["monitor_address"]),
                monitor_conf["name"],
                monitor_conf["group"],
                runner,
            )
        await component.set_ready(True)
        await component.wait_closed()
    elif "event_server_address" in hat_conf:
        async_group = aio.Group()
        client = await hat.event.eventer.client.connect(
            _parse_tcp(hat_conf["event_server_address"]),
            "aimm_client",
            subscriptions=subscriptions,
        )
        _bind_resource(async_group, client)
        await async_group.spawn(
            run, conf=conf, component=None, server_data=None, client=client
        )
    else:
        mlog.debug("running without hat compatibility")
        await run(conf)


async def run(conf, component=None, server_data=None, client=None):
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
            # TODO: filthy hack for sake of bw compatibility without too much
            #  refactoring, to be corrected ASAP
            client._events_cb = partial(_events_cb, proxies)

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


async def _events_cb(proxies, _, events):
    for proxy in proxies:
        proxy_events = [
            e for e in events if proxy.subscription.matches(e.type)
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


def _parse_tcp(address: str):
    url = urlparse(address)
    return tcp.Address(host=url.hostname, port=url.port)


if __name__ == "__main__":
    sys.exit(main())
