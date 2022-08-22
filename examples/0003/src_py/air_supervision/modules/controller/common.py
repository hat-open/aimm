from air_supervision.modules.controller import model
from dataclasses import dataclass
from typing import Any, List
import abc
import hat.aio
import hat.event.server.common
import hat.event.server.module_engine
import logging
import numpy as np

mlog = logging.getLogger(__name__)
json_schema_id = None
json_schema_repo = None
_source_id = 0


class ReadingsHandler:
    def __init__(self):
        self.readings = []
        self.readings_times = []
        self.size = 0
        self.read_index = 0

    def append(self, reading, reading_time):
        self.readings.append(reading)
        self.readings_times.append(reading_time)
        self.size += 1

    def get_first_n_readings(self, n):
        return self.readings[:n].copy(), self.readings_times[:n].copy()

    def remove_first_n_readings(self, n):
        self.readings = self.readings[n:]
        self.readings_times = self.readings_times[n:]
        self.size -= n


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
    engine: hat.event.server.module_engine.ModuleEngine = None
    source: hat.event.server.common.Source = None
    subscription: hat.event.server.common.Subscription = None
    model_family: str = None
    supported_models: List[str] = None
    batch_size: int = 48
    vars: dict = None


class GenericReadingsModule(hat.event.server.common.Module, abc.ABC):

    def __init__(self, builder: ReadingsModuleBuilder):
        self._engine = builder.engine
        self._source = builder.source
        self._subscription = builder.subscription
        self._model_family = builder.model_family
        self._supported_models = builder.supported_models
        self._batch_size = builder.batch_size
        self.vars = builder.vars

        self._async_group = hat.aio.Group()

        self.readings_control = ReadingsHandler()
        self._current_model_name = None

        self.fit_data_ind = 0
        self.fit_data_lim = 5

        self._models = {}
        self._request_ids = {}

        self.lock = FitLock()

    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def create_session(self):
        return Session(self._engine, self, self._async_group.create_subgroup())

    def process(self, event):
        selector = event.event_type[0]
        if selector == 'aimm':
            yield from self._process_aimm(event)
        elif selector == 'gui':
            yield from self._process_reading(event)
        elif selector == 'user_action':
            yield from self._process_user_action(event)

    @abc.abstractmethod
    def transform_row(self,
                      value: float,
                      timestamp: float) -> Any:
        """Convert a given value and timestamp into a table row, used to create
        a table input for the AIMM model.

        value: received measurement
        timestamp: time of measurement

        Returns:
            Row representation"""

    def _process_aimm(self, event):
        msg_type = event.event_type[1]
        if msg_type == 'state':
            yield from self._update_model_ids(event)
        elif msg_type == 'action':
            yield from self._process_action(event)

    def _update_model_ids(self, event):
        if not event.payload.data['models'] or not self._models:
            return

        for model_id, model_name in event.payload.data['models'].items():
            model_name = model_name.rsplit('.', 1)[-1]

            for saved_model_name, saved_model_inst in self._models.items():
                if model_name == saved_model_name:
                    saved_model_inst.set_id(model_id)

        yield self._message(event.payload.data, 'model_state')

    def _process_action(self, event):
        payload = event.payload.data
        instance = payload.get('request_id')['instance']
        if (instance not in self._request_ids
                or payload.get('status') != 'DONE'):
            return

        type_, model_name = self._request_ids[instance]

        if type_ == model.ReturnType.CREATE:
            self.lock.created(model_name)
            self._async_group.spawn(self._models[model_name].fit)

            yield self._message(model_name, 'new_current_model')
            params = self._models[model_name].get_default_setting()
            yield self._message(params, 'setting')
        elif type_ == model.ReturnType.FIT:
            self.lock.fitted()
        elif type_ == model.ReturnType.PREDICT:
            yield from self._process_predict(event)
        else:
            del self._request_ids[instance]

    def _process_predict(self, event):
        values, timestamps = self.readings_control.get_first_n_readings(
            self._batch_size)
        results = np.array(event.payload.data['result'])

        if self.vars['model_family'] == 'anomaly':
            results = results[:, -1]
            values = [i[0] for i in values]

        if isinstance(results, np.ndarray):
            results = results.tolist()

        for t, r, v in zip(timestamps, results, values):
            yield _register_event(('gui', 'system', 'timeseries',
                                   self.vars['model_family']),
                                  {'timestamp': t,
                                   'result': r,
                                   'value': v})

    def _process_reading(self, event):
        yield self._message(self.vars["supported_models"], 'supported_models')
        if not self.lock.can_fit():
            return
        row = self.transform_row(event.payload.data['value'],
                                 event.payload.data['timestamp'])
        self.readings_control.append(row, event.payload.data["timestamp"])

        if self.readings_control.size != self._batch_size:
            return

        model_input, _ = self.readings_control.get_first_n_readings(
            self._batch_size)
        current_model = self._models[self.lock.current_model]
        self._async_group.spawn(current_model.predict, [model_input])

        self.readings_control.remove_first_n_readings(
            self._batch_size if self._model_family == 'anomaly'
            else self._batch_size // 2)

    def _process_user_action(self, event):
        user_action = event.event_type[-1]
        if user_action == 'setting_change':
            self._process_setting_change(event)
        elif user_action == 'model_change':
            yield from self._process_model_change(event)

    def _process_setting_change(self, event):
        kw = dict(event.payload.data)
        del kw['action']
        current_model = self._models[self.lock.current_model]
        self._async_group.spawn(current_model.fit, **kw)

    def _process_model_change(self, event):
        received_model_name = event.payload.data['model']

        if received_model_name in self._models:
            self.lock.current_model = received_model_name
            yield self._message(received_model_name, 'new_current_model')

        self.lock.changed(received_model_name)
        new_model = model.factory(self._model_family, received_model_name,
                                  self)

        self._models[received_model_name] = new_model
        self._async_group.spawn(new_model.create_instance)

    def _message(self, data, type_name):
        return _register_event(('gui', 'log', self._model_family, type_name),
                               data)


class Session(hat.event.server.common.ModuleSession):

    def __init__(self, engine, module, group):
        self._engine = engine
        self._module = module
        self._async_group = group

    @property
    def async_group(self):
        return self._async_group

    async def process(self, changes):
        new_events = []
        for event in changes:
            for new_event in self._module.process(event):
                proc_event = self._engine.create_process_event(
                    self._module._source, new_event)
                new_events.append(proc_event)
        return new_events


def _register_event(event_type, payload, source_timestamp=None):
    return hat.event.server.common.RegisterEvent(
        event_type=event_type,
        source_timestamp=source_timestamp,
        payload=hat.event.server.common.EventPayload(
            type=hat.event.server.common.EventPayloadType.JSON,
            data=payload))
