import abc
import csv
from datetime import datetime
from enum import Enum
from itertools import count
import numpy
from hat.event import common
from typing import Any
import hat.aio
import hat.event.common
import hat.event.server.engine
import logging

mlog = logging.getLogger(__name__)


class Controller(hat.event.common.Module):
    def __init__(self, conf, engine, source):
        self._engine = engine
        self._source = source
        self._model_family = conf["model_family"]
        self._batch_size = conf["batch_size"]
        self._min_readings = conf["min_readings"]
        self._models_conf = conf["models"]

        self._subscription = hat.event.common.create_subscription([
            ("user_action", self._model_family, "*"),
            ("aimm", "*"),
            ("gui", "system", "timeseries", "reading"),
        ])

        self._model_prefix = f"air_supervision.aimm.{self._model_family}"

        self._async_group = hat.aio.Group()

        self._readings = []
        self._models = {}
        self._request_ids = {}
        self._current_model = None
        self._locked = True

    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def process(self, source, event):
        events = []
        selector = event.type[0]
        if selector == "aimm":
            events = self._process_aimm(event)
        elif selector == "gui":
            events = self._process_reading(event)
        elif selector == "user_action":
            events = self._process_user_action(event)
        return list(events)

    async def register_with_action_id(
        self,
        model_type,
        request_id,
        return_type,
        events
    ):
        await self._engine.register(self._source, events)
        self._request_ids[request_id] = (return_type, model_type)


    def _process_aimm(self, event):
        msg_type = event.type[1]
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

        if type_ == ReturnType.CREATE:
            self._current_model = model_name
            self._async_group.spawn(self._models[model_name].fit)

            yield self._message(model_name, "new_current_model")
            params = self._models[model_name].hyperparameters
            yield self._message(params, "setting")
        elif type_ == ReturnType.FIT:
            self._locked = False
        elif type_ == ReturnType.PREDICT:
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
        yield self._message(list(self._models_conf), "supported_models")
        if self._locked:
            return
        row = self._transform_row(
            event.payload.data["value"], event.payload.data["timestamp"]
        )
        self._readings.append((row, event.payload.data["timestamp"]))

        if len(self._readings) != self._batch_size:
            return

        if not self._readings[0][1].endswith("00:00:00"):
            self._readings = self._readings[1:]
            return

        model_input, _ = zip(*self._readings[: self._batch_size])
        current_model = self._models[self._current_model]
        self._async_group.spawn(current_model.predict, [model_input])

        total_readings = len(self._readings)
        self._readings = self._readings[total_readings - self._min_readings :]

    def _transform_row(self, value: float, timestamp: str) -> Any:
        """Convert a given value and timestamp into a table row, used to create
        a table input for the AIMM model.

        value: received measurement
        timestamp: time of measurement

        Returns:
            Row representation"""
        if self._model_family == "forecast":
            return value
        d = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        return [
            float(value),
            d.hour,
            int((d.hour >= 7) & (d.hour <= 22)),
            d.weekday(),
            int(d.weekday() < 5),
        ]

    def _process_user_action(self, event):
        user_action = event.type[-1]
        if user_action == "setting_change":
            self._process_setting_change(event)
        elif user_action == "model_change":
            yield from self._process_model_change(event)

    def _process_setting_change(self, event):
        kw = dict(event.payload.data)
        del kw["action"]
        current_model = self._models[self._current_model]
        self._async_group.spawn(current_model.fit, **kw)

    def _process_model_change(self, event):
        received_model_name = event.payload.data["model"]

        if received_model_name in self._models:
            self._current_model = received_model_name
            yield self._message(received_model_name, "new_current_model")

        self._current_model = received_model_name
        self._locked = True
        new_model = Model(
            self._model_family,
            self,
            f"{self._model_prefix}.{received_model_name}",
            self._models_conf[received_model_name],
        )

        self._models[new_model.model_class] = new_model
        self._async_group.spawn(new_model.create_instance)

    def _message(self, data, type_name):
        return _register_event(
            ("gui", "log", self._model_family, type_name), data
        )


info = common.ModuleInfo(create=Controller)
request_id_counter = count(0)


class ReturnType(Enum):
    CREATE = 1
    FIT = 2
    PREDICT = 3


class Model(abc.ABC):
    def __init__(self, model_family, module, model_class, hyperparameters):
        self._model_family = model_family
        self._module = module

        self._id = None
        self._model_class = model_class

        self._hyperparameters = hyperparameters
        self._executor = hat.aio.create_executor()

    @property
    def model_class(self):
        return self._model_class

    @property
    def hyperparameters(self):
        return self._hyperparameters

    def set_id(self, model_id):
        self._id = model_id

    async def fit(self, **kwargs):
        """Method used to invoke model fitting.

        Args:
            **kwargs: matches concrete model's hyperparameters"""
        if not self._id or self._model_family not in ("anomaly", "forecast"):
            return

        dataset_fn = _ext_forecast_dataset
        if self._model_family == "anomaly":
            dataset_fn = _ext_anomaly_dataset
        data = {
            "args": await self._executor(dataset_fn),
            "kwargs": kwargs,
            "request_id": str(next(request_id_counter)),
        }
        await self._register_event(
            ("aimm", "fit", self._id), data, ReturnType.FIT
        )

    async def create_instance(self):
        event_type = ("aimm", "create_instance")
        data = {
            "model_type": self._model_class,
            "args": [],
            "kwargs": self.hyperparameters,
            "request_id": str(next(request_id_counter)),
        }

        await self._register_event(event_type, data, ReturnType.CREATE)

    async def predict(self, model_input):
        event_type = ("aimm", "predict", self._id)
        data = {
            "args": model_input,
            "kwargs": {},
            "request_id": str(next(request_id_counter)),
        }

        await self._register_event(event_type, data, ReturnType.PREDICT)

    async def _register_event(self, event_type, data, return_type):
        request_id = data["request_id"]
        await self._module.register_with_action_id(
            self._model_class,
            request_id,
            return_type,
            [
                hat.event.common.RegisterEvent(
                    type=event_type,
                    source_timestamp=None,
                    payload=hat.event.common.EventPayloadJson(data),
                )
            ]
        )


def _ext_line_generator():
    with open("dataset/ambient_temperature_system_failure.csv", "r") as f:
        reader = csv.reader(f, delimiter="\t")
        for i, line in enumerate(reader):
            if not i:
                continue
            yield line


def _ext_forecast_dataset():
    values = []
    for line in _ext_line_generator():
        raw_value = float(line[0].split(",")[1])
        values.append((float(raw_value) - 32) * 5 / 9)

    x, y = [], []
    for i in range(48, len(values) - 24, 24):
        x.append(values[i - 48 : i])
        y.append(values[i : i + 24])

    x, y = numpy.array(x), numpy.array(y)

    fit_start = int(len(x) * 0.25)
    return [x[fit_start:].tolist(), y[fit_start:].tolist()]


def _ext_anomaly_dataset():
    train_data = []
    for line in _ext_line_generator():
        timestamp = datetime.strptime(
            line[0].split(",")[0], "%Y-%m-%d %H:%M:%S"
        )
        value = float(line[0].split(",")[1])
        value = (float(value) - 32) * 5 / 9
        train_data.append([
            value,
            timestamp.hour,
            int((timestamp.hour >= 7) & (timestamp.hour <= 22)),
            timestamp.weekday(),
            int(timestamp.weekday() < 5),
        ])
    fit_start = int(len(train_data) * 0.25)
    return [train_data[fit_start:], None]


def _register_event(event_type, payload, source_timestamp=None):
    return hat.event.common.RegisterEvent(
        type=event_type,
        source_timestamp=source_timestamp,
        payload=hat.event.common.EventPayloadJson(data=payload),
    )
