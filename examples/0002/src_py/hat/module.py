from hat import aio
from hat import json
from hat.event.server import common
import asyncio
import itertools
import logging


mlog = logging.getLogger(__name__)

json_schema_id = "hat-aimm://module.yaml#"
json_schema_repo = json.SchemaRepository(
    json.decode(
        """
---
id: 'hat-aimm://module.yaml#'
type: object
...
""",
        format=json.Format.YAML,
    )
)


async def create(conf, engine, source):
    module = Module()
    module._gw_prefix = ("gateway", "gateway", "device", "device")
    module._subscription = common.Subscription(
        [
            ("measurement", "?", "?"),
            (*module._gw_prefix, "gateway", "running"),
            ("aimm", "state"),
            ("aimm", "response"),
        ]
    )

    global _source_id
    module._source = source

    module._async_group = aio.Group()
    module._engine = engine
    module._model_id = None
    module._create_model_request_id = None
    module._predict_request_id = None
    module._measurements = {}

    module._predict_task = None
    module._request_gen = itertools.count(1)

    return module


class Module(common.Module):
    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def process(self, source, e):
        if source == self._source:
            return

        payload = e.payload.data
        if e.event_type == (*self._gw_prefix, "gateway", "running"):
            if payload is False:
                yield _register_event(
                    (
                        "gateway",
                        "gateway",
                        "device",
                        "device",
                        "system",
                        "enable",
                    ),
                    True,
                )

        elif e.event_type[0] == "measurement":
            self._measurements = json.set_(
                self._measurements, list(e.event_type[1:]), payload
            )
            if self._predict_task is None:
                self._predict_task = self.async_group.spawn(
                    self._predict, self._source
                )

        elif e.event_type == ("aimm", "state"):
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

        elif e.event_type == ("aimm", "response"):
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


def _register_event(event_type, payload):
    return common.RegisterEvent(
        event_type=event_type,
        source_timestamp=None,
        payload=common.EventPayload(common.EventPayloadType.JSON, payload),
    )
