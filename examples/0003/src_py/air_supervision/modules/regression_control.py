from hat import util
import hat.aio
import hat.event.server.common
from aimm.client import repl
from enum import Enum

import sys
import os
from datetime import datetime
sys.path.insert(0, '../../')
import importlib
# from src_py.air_supervision.modules.SVR import MultiOutputSVR, constant
from air_supervision.modules.regression_model_generic import RETURN_TYPE
import numpy as np
import logging


mlog = logging.getLogger(__name__)
json_schema_id = None
json_schema_repo = None
_source_id = 0


async def create(conf, engine):
    module = ReadingsModule()
    # module.model_control = ModelControl()

    global _source_id
    module._source = hat.event.server.common.Source(
        type=hat.event.server.common.SourceType.MODULE,
        name=__name__,
        id=_source_id)
    _source_id += 1

    module._subscription = hat.event.server.common.Subscription([
        ('aimm', '*'),
        ('gui', 'system', 'timeseries', 'reading'),
        ('back_action', '*')])
    module._async_group = hat.aio.Group()
    module._engine = engine

    module._model_ids = {}
    module._current_model_name = None

    module._predictions = []
    module._predictions_times = []

    module._readings_done = None
    module._readings = []

    module.data_tracker = 0

    module._request_id = None

    module._MODELS = {}
    module._request_ids = {}

    return module


class ReadingsModule(hat.event.server.common.Module):

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
                [_register_event(('gui', 'log', type_name), data)])

        try:
            self._async_group.spawn(send_log_message)
        except:
            pass


    # def process_state(self, event):
    #     if not event.payload.data['models'] or not self._MODELS:
    #         return
    #
    #     for model_id, model_name in event.payload.data['models'].items():
    #         model_name = model_name.rsplit('.', 1)[-1]
    #         for m_name, model_inst in self._MODELS.items():
    #             if model_name == m_name:
    #                 model_inst.set_id(model_id)
    #
    #     self.send_message(event, 'model_state')

    def update_models_ids(self, event):
        if not event.payload.data['models'] or not self._MODELS:
            return

        for aimm_model_id, aimm_model_name in event.payload.data['models'].items():
            aimm_model_name = aimm_model_name.rsplit('.', 1)[-1]

            for saved_model_name, saved_model_inst in self._MODELS.items():
                if aimm_model_name == saved_model_name:
                    saved_model_inst.set_id(aimm_model_id)

        self.send_message(event.payload.data, 'model_state')


    def process_action(self, event):
        if (request_instance := event.payload.data.get('request_id')['instance']) in self._request_ids \
                and event.payload.data.get('status') == 'DONE':

            request_type, model_name = self._request_ids[request_instance]
            del self._request_ids[request_instance]

            if request_type == RETURN_TYPE.CREATE:
                # self._current_model_name = model_name
                # self._async_group.spawn(self._MODELS[model_name].fit)
                try:
                    self._async_group.spawn(self._MODELS[model_name].fit)
                    self.send_message(model_name, 'new_current_model')
                    hyperparameters = self._MODELS[model_name].get_default_setting()
                    self.send_message(hyperparameters, 'setting')
                except:
                    pass

            if request_type == RETURN_TYPE.FIT:
                self._current_model_name = model_name
                pass

            if request_type == RETURN_TYPE.PREDICT:

                def _process_event(event_type, payload, source_timestamp=None):
                    return self._engine.create_process_event(
                        self._source,
                        _register_event(event_type, payload, source_timestamp))

                return [
                    _process_event(
                        ('gui', 'system', 'timeseries', 'forecast'), v)
                    for v in event.payload.data['result']]

            # vals = np.array(self._predictions[-5:])[:, 0]
            #
            # org_vals_from_aimm = np.array(event.payload.data['result'])[:, 0]
            #
            # results = np.array(event.payload.data['result'])[:, -1]
            #
            # rez = [
            #     _process_event(
            #         ('gui', 'system', 'timeseries', 'forecast'), {
            #             'timestamp': t,
            #             'is_anomaly': r,
            #             'value': v
            #         })
            #     for r, t, v in zip(results, self._predictions_times[-5:], vals)]
            #
            # self._predictions_times = self._predictions_times[-5:]
            # self._predictions = self._predictions[-5:]
            # return rez



    def process_back_value(self, event):
        {
            'setting_change': self.process_setting_change,
            'model_change': self.process_model_change
        }[event.event_type[-1]](event)


    # def process_back_value(self, event):
    #
    #     model_n = 'MultiOutputSVR'
    #     if 'model' in event.payload.data:
    #         model_n = event.payload.data['model']
    #
    #     # IGNORED ON FIRST RUN
    #     for model_name, model_inst in self._MODELS.items():
    #         if model_n == model_name:
    #             self._current_model_name = model_name
    #             return
    #
    #     MyClass = getattr(importlib.import_module("air_supervision.modules.regression_models"), model_n)
    #
    #     self._MODELS[model_n] = MyClass(self)
    #
    #     self._async_group.spawn(self._MODELS[model_n].create_instance)

    def process_model_change(self, event):
        received_model_name = event.payload.data['model']

        if received_model_name in self._MODELS:
            self._current_model_name = received_model_name
            self.send_message(received_model_name, 'new_current_model')
            return

        self._MODELS[received_model_name] = \
            getattr(importlib.import_module("air_supervision.modules.regression_models"),
                    received_model_name)(self, received_model_name)

        try:
            self._async_group.spawn(self._MODELS[received_model_name].create_instance)
        except:
            pass


    def process_setting_change(self, event):

        kw = event.payload.data
        del kw['action']

        try:
            self._async_group.spawn(self._MODELS[self._current_model_name].fit, **kw)
        except:
            pass


    def process_aimm(self, event):

        if event.event_type[1] == 'state':
            return self.update_models_ids(event)

        elif event.event_type[1] == 'action':
            return self.process_action(event)



    def process_reading(self, event):

        self.send_message(["MultiOutputSVR", "linear", "constant"], 'supported_models')

        self._readings += [event.payload.data]

        if len(self._readings) == 48:
            model_input = self._readings
            self._readings = self._readings[:24]

            if self._current_model_name:
                self._async_group.spawn(self._MODELS[self._current_model_name].predict, model_input)

        # if self._current_model_name:
        #     d = event.payload.data['timestamp']
        #     predict_row = [float(event.payload.data['value']),
        #                    d.hour,
        #                    int((d.hour >= 7) & (d.hour <= 22)),
        #                    d.weekday(),
        #                    int(d.weekday() < 5)]
        #
        #     self._predictions_times.append(str(d))
        #     self._predictions.append(predict_row)
        #
        #     self.data_tracker += 1
        #     if self.data_tracker >= 5:
        #
        #         try:
        #             self._async_group.spawn(
        #                 self._MODELS[self._current_model_name].predict, np.array(self._predictions[-5:]))
        #         except:
        #             pass
        #         self.data_tracker = 0

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
