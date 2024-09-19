from hat import aio
from hat import json
from hat.event import common
import asyncio
import itertools
import logging


mlog = logging.getLogger(__name__)


class Module(common.Module):
    def __init__(self, _, engine, source):
        self._gw_prefix = ("gateway", "gateway", "device", "device")
        self._subscription = common.create_subscription([
            ("measurement", "?", "?"),
            ("event", "?", "eventer", "gateway"),
            ("aimm", "state"),
            ("aimm", "response"),
        ])

        self._source = source

        self._async_group = aio.Group()
        self._engine = engine
        self._model_id = None
        self._create_model_request_id = None
        self._predict_request_id = None
        self._measurements = {}

        self._predict_task = None
        self._request_gen = itertools.count(1)

    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def process(self, source, e):
        return [
            event async for event in self._async_generator_process(source, e)
        ]

    async def _async_generator_process(self, source, e):
        if source == self._source:
            return

        payload = e.payload.data
        if e.type == ("event", "0", "eventer", "gateway"):
            if payload == "CONNECTED":
                yield _register_event(
                    (
                        "gateway",
                        "device",
                        "device",
                        "system",
                        "enable",
                    ),
                    True,
                )

        elif e.type[0] == "measurement":
            self._measurements = json.set_(
                self._measurements, list(e.type[1:]), payload
            )
            if self._predict_task is None:
                self._predict_task = self.async_group.spawn(
                    self._predict, self._source
                )

        elif e.type == ("aimm", "state"):
            if self._model_id is not None:
                return
            if self._model_id in payload["models"]:
                return
            if self._create_model_request_id is not None:
                return

            self._model_id = None
            self._create_model_request_id = str(next(self._request_gen))
            request_ev = _register_event(
                ("aimm", "create_instance"),
                {
                    "model_type": "aimm_plugins.power.StateEstimator",
                    "args": [],
                    "kwargs": {},
                    "request_id": self._create_model_request_id,
                },
            )
            yield request_ev

        elif e.type == ("aimm", "response"):
            if payload["request_id"] == self._create_model_request_id:
                self._model_id = str(payload["result"])
            elif payload["request_id"] == self._predict_request_id:
                result = payload["result"]
                if result is None:
                    return
                bus_ids = set(result["vm_pu"])
                bus_ids |= set(result["va_degree"])
                bus_ids |= set(result["p_mw"])
                bus_ids |= set(result["q_mvar"])
                for bus_id in bus_ids:
                    yield _register_event(
                        ("estimation", bus_id, "v"), result["vm_pu"][bus_id]
                    )
                    yield _register_event(
                        ("estimation", bus_id, "va"),
                        result["va_degree"][bus_id],
                    )
                    yield _register_event(
                        ("estimation", bus_id, "p"), result["p_mw"][bus_id]
                    )
                    yield _register_event(
                        ("estimation", bus_id, "q"), result["q_mvar"][bus_id]
                    )

    async def _predict(self, source):
        await asyncio.sleep(1)  # buffer measurements
        try:
            if self._model_id is None:
                return
            self._predict_request_id = str(next(self._request_gen))
            await self._engine.register(
                source,
                [
                    _register_event(
                        ("aimm", "predict", self._model_id),
                        {
                            "args": [
                                list(_measurements_to_arg(self._measurements))
                            ],
                            "kwargs": {},
                            "request_id": self._predict_request_id,
                        },
                    )
                ],
            )
        finally:
            self._predict_task = None


def _measurements_to_arg(measurements):
    for bus_id, bus_measurements in measurements.items():
        for m_type, value in bus_measurements.items():
            yield {
                "type": m_type,
                "element_type": "bus",
                "value": value,
                "std_dev": 10,
                "element": int(bus_id),
                "side": None,
            }


info = common.ModuleInfo(create=Module)


def _register_event(event_type, payload):
    return common.RegisterEvent(
        type=event_type,
        source_timestamp=None,
        payload=common.EventPayloadJson(payload),
    )
