import importlib
import logging
from typing import Any

from hat import aio
import hat.event.component
import hat.monitor.component
import hat.event.common
import hat.event.eventer.client
from hat.drivers import tcp
import aimm.server.engine

mlog = logging.getLogger(__name__)


class MainRunner(aio.Resource):
    def __init__(self, conf):
        self._conf = conf
        self._group = aio.Group()

        self._group.spawn(self._run)

    @property
    def async_group(self) -> aio.Group:
        return self._group

    async def _run(self):
        if "hat" in self._conf:
            child_runner = HatRunner(self._conf)
        else:
            mlog.debug("running without hat compatibility")
            child_runner = AIMMRunner(self._conf, client=None)
            _bind_resource(self._group, child_runner)
        try:
            await child_runner.wait_closing()
        except Exception as e:
            mlog.error("main runner loop error: %s", e, exc_info=e)
        finally:
            await aio.uncancellable(child_runner.async_close())


class HatRunner(aio.Resource):
    def __init__(self, conf):
        self._conf = conf
        self._group = aio.Group()

        self._aimm_runner = None
        self._hat_component = None
        self._eventer_client = None

        self._subscriptions = []
        self._backend_subscription = None
        module = importlib.import_module(conf["backend"]["module"])
        if hasattr(module, "create_subscription"):
            subscription = module.create_subscription(conf["backend"])
            self._subscriptions.extend(subscription)
            self._backend_subscription = hat.event.common.create_subscription(
                subscription
            )

        self._control_subscriptions = []
        for control_id, control_conf in enumerate(conf["control"]):
            module = importlib.import_module(control_conf["module"])
            if hasattr(module, "create_subscription"):
                subscription = module.create_subscription(control_conf)
                self._subscriptions.extend(subscription)
                self._control_subscriptions.append(
                    (
                        hat.event.common.create_subscription(subscription),
                        control_id,
                    )
                )

        self._group.spawn(self._run)

    @property
    def async_group(self) -> aio.Group:
        return self._group

    async def _run(self):
        hat_conf = self._conf["hat"]
        if monitor_conf := hat_conf.get("monitor_component"):
            if event_server_group := monitor_conf.get("event_server_group"):

                async def events_cb(_, __, events):
                    await self._on_events(events)

                self._hat_component = await hat.event.component.connect(
                    addr=tcp.Address(
                        host=monitor_conf["host"], port=monitor_conf["port"]
                    ),
                    name=self._conf["name"],
                    group=monitor_conf["group"],
                    server_group=event_server_group,
                    client_name=f"aimm/{self._conf["name"]}",
                    runner_cb=(
                        lambda _, __, client: self._create_aimm_runner(client)
                    ),
                    events_cb=events_cb,
                    eventer_kwargs={"subscriptions": self._subscriptions},
                )
            else:
                self._hat_component = await hat.monitor.component.connect(
                    addr=tcp.Address(
                        host=monitor_conf["host"], port=monitor_conf["port"]
                    ),
                    name=self._conf["name"],
                    group=monitor_conf["group"],
                    runner_cb=lambda _: self._create_aimm_runner(None),
                )
            await self._hat_component.set_ready(True)
            _bind_resource(self._group, self._hat_component)
        elif eventer_conf := hat_conf.get("eventer_server"):

            async def on_eventer_events(_, events):
                await self._on_events(events)

            self._eventer_client = await hat.event.eventer.connect(
                addr=tcp.Address(eventer_conf["host"], eventer_conf["port"]),
                client_name=self._conf["name"],
                status_cb=None,
                events_cb=on_eventer_events,
                subscriptions=self._subscriptions,
            )
            _bind_resource(self._group, self._eventer_client)
            self._create_aimm_runner(self._eventer_client)

        try:
            await self._group.wait_closing()
        except Exception as e:
            mlog.error("unhandled exception in hat runner: %s", e, exc_info=e)
        finally:
            await aio.uncancellable(self._cleanup())

    async def _cleanup(self):
        if self._aimm_runner:
            await self._aimm_runner.async_close()
        if self._hat_component:
            await self._hat_component.async_close()
        if self._eventer_client:
            await self._eventer_client.async_close()

    def _create_aimm_runner(self, eventer_client):
        self._aimm_runner = AIMMRunner(conf=self._conf, client=eventer_client)
        _bind_resource(self._group, self._aimm_runner)
        return self._aimm_runner

    async def _on_events(self, events):
        if self._aimm_runner is None:
            return
        if self._backend_subscription:
            backend_events = [
                e for e in events if self._backend_subscription.matches(e.type)
            ]
            await self._aimm_runner.notify_backend(backend_events)
        for subscription, control_id in self._control_subscriptions:
            control_events = [
                e for e in events if subscription.matches(e.type)
            ]
            await self._aimm_runner.notify_control(control_id, control_events)


class AIMMRunner(aio.Resource):
    def __init__(self, conf, client):
        self._conf = conf
        self._group = aio.Group()
        self._client = client
        self._module_map = {}

        self._backend = None
        self._engine = None
        self._controls = []

        self._group.spawn(self._run)

    @property
    def async_group(self) -> aio.Group:
        return self._group

    async def notify_backend(self, data: Any):
        await self._backend.process_events(data)

    async def notify_control(self, control_id: int, data: Any):
        await self._controls[control_id].process_events(data)

    async def _run(self):
        async for resource in self._create_resources():
            _bind_resource(self._group, resource)

        try:
            await self._group.wait_closing()
        except Exception as e:
            mlog.error("error in aimm runner: %s", e, exc_info=e)

    async def _create_resources(self):
        self._backend = await self._create_backend(self._conf["backend"])
        yield self._backend

        self._engine = await aimm.server.engine.create(
            self._conf["engine"], self._backend
        )
        yield self._engine

        for control_conf in self._conf["control"]:
            control = await self._create_control(control_conf, self._engine)
            self._controls.append(control)
            yield control

    async def _create_backend(self, backend_conf):
        module = importlib.import_module(backend_conf["module"])
        backend = await aio.call(module.create, backend_conf, self._client)
        self._module_map[self._conf["backend"]["module"]] = backend
        return backend

    async def _create_control(self, control_conf, engine):
        module = importlib.import_module(control_conf["module"])
        control = await aio.call(
            module.create, control_conf, engine, self._client
        )
        self._module_map[control_conf["module"]] = control
        return control


def _bind_resource(group, resource):
    group.spawn(aio.call_on_cancel, resource.async_close)
    group.spawn(aio.call_on_done, resource.wait_closing(), group.close)
