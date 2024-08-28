from hat import aio
import asyncio
import base64
import contextlib
import hat.event.common
import logging

from aimm.server import common
from aimm import plugins


mlog = logging.getLogger(__name__)


def create_subscription(conf):
    return hat.event.common.create_subscription(
        [tuple([*p, "*"]) for p in conf["event_prefixes"].values()]
    )


async def create(conf, engine, event_client):
    common.json_schema_repo.validate("aimm://server/control/event.yaml#", conf)
    if event_client is None:
        raise ValueError(
            "attempting to create event control without hat compatibility"
        )

    control = EventControl()

    control._client = event_client
    control._engine = engine
    control._async_group = aio.Group()
    control._event_prefixes = conf["event_prefixes"]
    control._state_event_type = conf["state_event_type"]
    control._action_state_event_type = conf["action_state_event_type"]
    control._executor = aio.create_executor()
    control._notified_state = {}
    control._in_progress = {}

    control._async_group.spawn(control._main_loop)

    control._notify_state()
    control._engine.subscribe_to_state_change(control._notify_state)

    return control


class EventControl(common.Control):
    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    def _notify_state(self):
        state_json = _state_to_json(self._engine)
        if state_json == self._notified_state:
            return
        self._client.register(
            [_register_event(self._state_event_type, state_json)]
        )
        self._notified_state = state_json

    async def _main_loop(self):
        def prefix_match(action_prefix, event):
            if action_prefix not in self._event_prefixes:
                return False
            return hat.event.common.matches_query_type(
                event.type, self._event_prefixes[action_prefix] + ["*"]
            )

        with contextlib.suppress(asyncio.CancelledError):
            while True:
                events = await self._client.receive()
                for event in events:
                    if prefix_match("create_instance", event):
                        self.async_group.spawn(self._create_instance, event)
                    if prefix_match("add_instance", event):
                        self.async_group.spawn(self._add_instance, event)
                    if prefix_match("update_instance", event):
                        self.async_group.spawn(self._update_instance, event)
                    if prefix_match("fit", event):
                        self.async_group.spawn(self._fit, event)
                    if prefix_match("predict", event):
                        self.async_group.spawn(self._predict, event)
                    if prefix_match("cancel", event):
                        self._cancel(event)

    async def _create_instance(self, event):
        try:
            data = event.payload.data
            model_type = data["model_type"]
            args = [await self._process_arg(arg) for arg in data["args"]]
            kwargs = {
                k: await self._process_arg(v)
                for k, v in data["kwargs"].items()
            }
            action = self._engine.create_instance(model_type, *args, **kwargs)
            self._register_action_state(event, "IN_PROGRESS")
            self._in_progress[data["request_id"]] = action
            try:
                model = await action.wait_result()
                self._register_action_state(event, "DONE", model.instance_id)
            except asyncio.CancelledError:
                self._register_action_state(event, "CANCELLED")
            finally:
                del self._in_progress[data["request_id"]]
        except Exception as e:
            mlog.warning(
                "instance creation failed with exception %s", e, exc_info=e
            )
            self._register_action_state(event, "FAILED")

    async def _add_instance(self, event):
        try:
            data = event.payload.data
            instance = await self._instance_from_json(
                data["instance"], data["model_type"]
            )
            model = await self._engine.add_instance(
                data["model_type"], instance
            )
            self._register_action_state(event, "DONE", model.instance_id)
        except Exception as e:
            mlog.warning(
                "add instance failed with exception %s", e, exc_info=e
            )
            self._register_action_state(event, "FAILED")

    async def _update_instance(self, event):
        try:
            event_prefix = self._event_prefixes.get("update_instance")
            instance_id = int(event.type[len(event_prefix)])
            data = event.payload.data
            model_type = data["model_type"]
            model = common.Model(
                model_type=data["model_type"],
                instance_id=instance_id,
                instance=await self._instance_from_json(
                    data["instance"], model_type
                ),
            )
            await self._engine.update_instance(model)
            self._register_action_state(event, "DONE")
        except Exception as e:
            mlog.warning(
                "update instance failed with exception %s", e, exc_info=e
            )
            self._register_action_state(event, "FAILED")

    async def _fit(self, event):
        try:
            event_prefix = self._event_prefixes["fit"]
            data = event.payload.data
            instance_id = int(event.type[len(event_prefix)])
            if instance_id not in self._engine.state["models"]:
                raise ValueError("instance {instance_id} not in state")
            args = [await self._process_arg(a) for a in data["args"]]
            kwargs = {
                k: await self._process_arg(v)
                for k, v in data["kwargs"].items()
            }

            action = self._engine.fit(instance_id, *args, **kwargs)
            self._register_action_state(event, "IN_PROGRESS")
            self._in_progress[data["request_id"]] = action
            try:
                await action.wait_result()
                self._register_action_state(event, "DONE")
            except asyncio.CancelledError:
                self._register_action_state(event, "CANCELLED")
            finally:
                del self._in_progress[data["request_id"]]
        except Exception as e:
            mlog.warning("fitting failed with exception %s", e, exc_info=e)
            self._register_action_state(event, "FAILED")

    async def _predict(self, event):
        try:
            event_prefix = self._event_prefixes["predict"]
            data = event.payload.data
            instance_id = int(event.type[len(event_prefix)])
            if instance_id not in self._engine.state["models"]:
                raise ValueError("instance {instance_id} not in state")
            args = [await self._process_arg(a) for a in data["args"]]
            kwargs = {
                k: await self._process_arg(v)
                for k, v in data["kwargs"].items()
            }

            action = self._engine.predict(instance_id, *args, **kwargs)
            self._register_action_state(event, "IN_PROGRESS")
            self._in_progress[data["request_id"]] = action
            try:
                prediction = await action.wait_result()
                self._register_action_state(event, "DONE", prediction)
            except asyncio.CancelledError:
                self._register_action_state(event, "CANCELLED")
            finally:
                del self._in_progress[data["request_id"]]
        except Exception as e:
            mlog.warning("prediction failed with exception %s", e, exc_info=e)

    def _cancel(self, event):
        request_event_id = event.payload.data
        if request_event_id in self._in_progress:
            self._in_progress[request_event_id].close()

    def _register_action_state(self, request_event, status, result=None):
        return self._client.register(
            [
                _register_event(
                    self._action_state_event_type,
                    {
                        "request_id": request_event.payload.data["request_id"],
                        "status": status,
                        "result": result,
                    },
                )
            ]
        )

    async def _process_arg(self, arg):
        if not (isinstance(arg, dict) and arg.get("type") == "data_access"):
            return arg
        return common.DataAccess(
            name=arg["name"], args=arg["args"], kwargs=arg["kwargs"]
        )

    async def _instance_from_json(self, instance_b64, model_type):
        return await self._executor(
            plugins.exec_deserialize,
            model_type,
            base64.b64decode(instance_b64),
        )


def _state_to_json(engine):
    return {
        "models": {
            instance_id: model.model_type
            for instance_id, model in engine.state["models"].items()
        },
        "actions": engine.state["actions"],
    }


def _register_event(event_type, payload, source_timestamp=None):
    return hat.event.common.RegisterEvent(
        type=tuple(event_type),
        source_timestamp=source_timestamp,
        payload=hat.event.common.EventPayloadJson(payload),
    )
