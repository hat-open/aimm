from air_supervision.modules.controller import model
from dataclasses import dataclass
from typing import Any, List, Tuple
import abc
import hat.aio
import hat.event.server.common
import hat.event.server.engine
import logging

mlog = logging.getLogger(__name__)
json_schema_id = None
json_schema_repo = None
_source_id = 0


class FitLock:
    def __init__(self):
        self.lock = True
        self.current_model = None

    def get_current_model(self):
        return self.current_model

    def can_fit(self):
        return not self.lock

    def can_predict(self):
        return not self.lock

    def created(self, model):
        self.current_model = model

    def changed(self, model):
        self.current_model = model
        self.lock = True

    def fitted(self):
        self.lock = False


@dataclass
class ReadingsModuleBuilder:
    engine: hat.event.server.engine.Engine = None
    source: hat.event.server.common.Source = None
    user_action_type: Tuple[str] = None
    model_family: str = None
    supported_models: List[str] = None
    batch_size: int = 48
    min_readings: int = 0


class GenericReadingsModule(hat.event.server.common.Module, abc.ABC):
    def __init__(self, builder: ReadingsModuleBuilder):
        self._engine = builder.engine
        self._source = builder.source
        self._model_family = builder.model_family
        self._supported_models = builder.supported_models
        self._batch_size = builder.batch_size
        self._min_readings = builder.min_readings

        self._subscription = hat.event.server.common.Subscription(
            [
                builder.user_action_type,
                ("aimm", "*"),
                ("gui", "system", "timeseries", "reading"),
            ]
        )

        self._async_group = hat.aio.Group()

        self._readings = []
        self._current_model_name = None

        self._models = {}
        self._request_ids = {}

        self._lock = FitLock()

    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    @abc.abstractmethod
    def transform_row(self, value: float, timestamp: float) -> Any:
        """Convert a given value and timestamp into a table row, used to create
        a table input for the AIMM model.

        value: received measurement
        timestamp: time of measurement

        Returns:
            Row representation"""

    async def process(self, source, event):
        selector = event.event_type[0]
        generator = None
        if selector == "aimm":
            generator = self._process_aimm(event)
        elif selector == "gui":
            generator = self._process_reading(event)
        elif selector == "user_action":
            generator = self._process_user_action(event)
        if generator:
            for e in generator:
                yield e

    def _process_aimm(self, event):
        msg_type = event.event_type[1]
        if msg_type == "state":
            yield from self._update_model_ids(event)
        elif msg_type == "action":
            yield from self._process_action(event)

    def _update_model_ids(self, event):
        if not event.payload.data["models"] or not self._models:
            return

        for model_id, model_name in event.payload.data["models"].items():
            for saved_model_name, saved_model_inst in self._models.items():
                if model_name == saved_model_name:
                    saved_model_inst.set_id(model_id)

        yield self._message(event.payload.data, "model_state")

    def _process_action(self, event):
        payload = event.payload.data
        request_id = payload["request_id"]
        if request_id not in self._request_ids:
            return
        if payload.get("status") != "DONE":
            return

        type_, model_name = self._request_ids[request_id]

        if type_ == model.ReturnType.CREATE:
            self._lock.created(model_name)
            self._async_group.spawn(self._models[model_name].fit)

            yield self._message(model_name, "new_current_model")
            params = self._models[model_name].hyperparameters
            yield self._message(params, "setting")
        elif type_ == model.ReturnType.FIT:
            self._lock.fitted()
        elif type_ == model.ReturnType.PREDICT:
            yield from self._process_predict(event)
        else:
            del self._request_ids[request_id]

    def _process_predict(self, event):
        values, timestamps = zip(*self._readings[: self._batch_size])
        values = [v[0] if isinstance(v, list) else v for v in values]
        results = event.payload.data["result"]

        for t, r, v in zip(timestamps, results, values):
            yield _register_event(
                ("gui", "system", "timeseries", self._model_family),
                {"timestamp": t, "result": r, "value": v},
            )

    def _process_reading(self, event):
        yield self._message(self._supported_models, "supported_models")
        if not self._lock.can_fit():
            return
        row = self.transform_row(
            event.payload.data["value"], event.payload.data["timestamp"]
        )
        self._readings.append((row, event.payload.data["timestamp"]))

        if len(self._readings) != self._batch_size:
            return

        if not self._readings[0][1].endswith("00:00:00"):
            self._readings = self._readings[1:]
            return

        model_input, _ = zip(*self._readings[: self._batch_size])
        current_model = self._models[self._lock.current_model]
        self._async_group.spawn(current_model.predict, [model_input])

        self._readings = self._readings[
            (len(self._readings) - self._min_readings) :
        ]

    def _process_user_action(self, event):
        user_action = event.event_type[-1]
        if user_action == "setting_change":
            self._process_setting_change(event)
        elif user_action == "model_change":
            yield from self._process_model_change(event)

    def _process_setting_change(self, event):
        kw = dict(event.payload.data)
        del kw["action"]
        current_model = self._models[self._lock.current_model]
        self._async_group.spawn(current_model.fit, **kw)

    def _process_model_change(self, event):
        received_model_name = event.payload.data["model"]

        if received_model_name in self._models:
            self._lock.current_model = received_model_name
            yield self._message(received_model_name, "new_current_model")

        self._lock.changed(received_model_name)
        new_model = model.factory(
            self._model_family, received_model_name, self
        )

        self._models[new_model.model_type] = new_model
        self._async_group.spawn(new_model.create_instance)

    def _message(self, data, type_name):
        return _register_event(
            ("gui", "log", self._model_family, type_name), data
        )


def _register_event(event_type, payload, source_timestamp=None):
    return hat.event.server.common.RegisterEvent(
        event_type=event_type,
        source_timestamp=source_timestamp,
        payload=hat.event.server.common.EventPayload(
            type=hat.event.server.common.EventPayloadType.JSON, data=payload
        ),
    )
