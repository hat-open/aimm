from hat import util
import hat.aio
import hat.event.server.common
# from aimm.client import repl
# from enum import Enum

import sys
import os
from datetime import datetime

sys.path.insert(0, '../../')
import importlib
# from src_py.air_supervision.modules.SVR import MultiOutputSVR, constant
from air_supervision.modules.model_generic import RETURN_TYPE
import numpy as np
import logging

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
        self.readings = np.append(self.readings, reading)
        self.readings_times = np.append(self.readings_times, reading_time)
        # if reading is array
        if isinstance(reading, np.ndarray):
            self.size += reading.shape[0]
        else:
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
        
        
class GenericReadingsModule(hat.event.server.common.Module):

    def __init__(self):
        super().__init__()

        self.readings_control = ReadingsHandler()
        self._current_model_name = None

        self.fit_data_ind = 0
        self.fit_data_lim = 5
        self._batch_size = 48

        self._MODELS = {}
        self._request_ids = {}
        
        self.lock = FitLock()
        
        self.vars = {}

    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def create_session(self):
        return ReadingsSession(self._engine, self,
                               self._async_group.create_subgroup())

    def send_message(self, data, type_name):

        async def send_log_message():

            await self._engine.register(
                self._source,
                [_register_event(('gui', 'log', self._model_type, type_name), data)])

        try:
            self._async_group.spawn(send_log_message)
        except:
            pass

    def update_models_ids(self, event):
        if not event.payload.data['models'] or not self._MODELS:
            return

        for aimm_model_id, aimm_model_name in event.payload.data['models'].items():
            aimm_model_name = aimm_model_name.rsplit('.', 1)[-1]

            for saved_model_name, saved_model_inst in self._MODELS.items():
                if aimm_model_name == saved_model_name:
                    saved_model_inst.set_id(aimm_model_id)

        self.send_message(event.payload.data, 'model_state')

    def process_predict(self, event):

        def _process_event(event_type, payload, source_timestamp=None):
            return self._engine.create_process_event(
                self._source,
                _register_event(event_type, payload, source_timestamp))

        values, timestamps = self.readings_control.get_first_n_readings(self._batch_size)
        results = np.array(event.payload.data['result'])

        if self.vars['model_type'] == 'anomaly':
            results = results[:, -1]

        ret = [
            _process_event(
                ('gui', 'system', 'timeseries', self.vars["model_type"]), {
                    'timestamp': t,
                    'result': r,
                    'value': v

                })
            for t, r, v in zip(timestamps, results, values)]

        self.readings_control.remove_first_n_readings(self._batch_size)
        return ret

    def process_action(self, event):
        if (request_instance := event.payload.data.get('request_id')['instance']) in self._request_ids \
                and event.payload.data.get('status') == 'DONE':

            request_type, model_name = self._request_ids[request_instance]

            if (request_type == RETURN_TYPE.A_CREATE) if self._model_type == 'anomaly' else (request_type == RETURN_TYPE.F_CREATE):
                self.lock.created(model_name)

                self._async_group.spawn(self._MODELS[model_name].fit)

                self.send_message(model_name, 'new_current_model')
                hyperparameters = self._MODELS[model_name].get_default_setting()
                self.send_message(hyperparameters, 'setting')

                return


            if (request_type == RETURN_TYPE.A_FIT) if self._model_type == 'anomaly' else (request_type == RETURN_TYPE.F_FIT):
                self.lock.fitted()
                # self._current_model_name = model_name
                return

            if (request_type == RETURN_TYPE.A_PREDICT) if self._model_type == 'anomaly' else (request_type == RETURN_TYPE.F_PREDICT):
                return self.process_predict(event)

            del self._request_ids[request_instance]

    def process_back_value(self, event):
        {
            'setting_change': self.process_setting_change,
            'model_change': self.process_model_change
        }[event.event_type[-1]](event)

    def process_model_change(self, event):
        # {'action': 'model_change', 'type': 'anomaly', 'model': 'Forest'}

        received_model_name = event.payload.data['model']

        if received_model_name in self._MODELS:
            self.lock.current_model = received_model_name
            self.send_message(received_model_name, 'new_current_model')
            return

        self.lock.changed(received_model_name)
        self._MODELS[received_model_name] = \
            getattr(importlib.import_module(self._import_module_name),
                    received_model_name)(self, received_model_name)

        try:
            self._async_group.spawn(self._MODELS[received_model_name].create_instance)
        except:
            breakpoint()

    def process_setting_change(self, event):

        kw = event.payload.data
        del kw['action']

        try:
            self._async_group.spawn(self._MODELS[self.lock.current_model].fit, **kw)
        except:
            pass

    def process_aimm(self, event):

        if event.event_type[1] == 'state':
            return self.update_models_ids(event)

        elif event.event_type[1] == 'action':
            return self.process_action(event)

    def transform_row(self, value, timestamp):
        raise NotImplementedError()

    def process_reading(self, event):
        self.send_message(self.vars["supported_models"], 'supported_models')

        if self.lock.can_fit():

            row = self.transform_row(event.payload.data['value'], event.payload.data['timestamp'])
            self.readings_control.append(row, event.payload.data["timestamp"])

            if self.readings_control.size >= self._batch_size:
                self.readings_control.size += self._batch_size

                model_input, _ = self.readings_control.get_first_n_readings(self._batch_size)

                # breakpoint()
                self._async_group.spawn(self._MODELS[self.lock.current_model].predict, [model_input.tolist()])


class ReadingsSession(hat.event.server.common.ModuleSession):

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

            result = {
                'aimm': self._module.process_aimm,
                'gui': self._module.process_reading,
                'back_action': self._module.process_back_value

            }[event.event_type[0]](event)

            if result:
                new_events.extend(result)

        return new_events


def _register_event(event_type, payload, source_timestamp=None):
    return hat.event.server.common.RegisterEvent(
        event_type=event_type,
        source_timestamp=source_timestamp,
        payload=hat.event.server.common.EventPayload(
            type=hat.event.server.common.EventPayloadType.JSON,
            data=payload))
