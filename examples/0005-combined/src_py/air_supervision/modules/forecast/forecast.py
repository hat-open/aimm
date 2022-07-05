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
from air_supervision.modules.forecast.regression_model_generic import RETURN_TYPE
import numpy as np
from air_supervision.modules.model_controller import ReadingsModule, ReadingsControl,_register_event
import logging

mlog = logging.getLogger(__name__)
json_schema_id = None
json_schema_repo = None
_source_id = 0


async def create(conf, engine):
    module = ForecastModule()

    global _source_id
    module._source = hat.event.server.common.Source(
        type=hat.event.server.common.SourceType.MODULE,
        name=__name__,
        id=_source_id)
    _source_id += 1

    module._subscription = hat.event.server.common.Subscription([
        ('aimm', '*'),
        ('gui', 'system', 'timeseries', 'reading'),
        ('back_action', 'forecast', '*')])
    module._async_group = hat.aio.Group()
    module._engine = engine

    module._model_ids = {}
    module._current_model_name = None

    module._predictions = []
    module._predictions_times = []

    module._readings_control = ReadingsControl()

    module._readings_done = None
    module._readings = []

    module.data_tracker = 0

    module._request_id = None
    module._model_type = 'forecast'
    module._import_module_name = "air_supervision.modules.forecast.regression_models"
    module._supported_models = ["MultiOutputSVR", "linear", "constant"]
    module._readings_control = ReadingsControl()
    module._MODELS = {}
    module._request_ids = {}
    module._batch_size = 48

    return module


class ForecastModule(ReadingsModule):
    def process_predict(self, event):
        def _process_event(event_type, payload, source_timestamp=None):
            return self._engine.create_process_event(
                self._source,
                _register_event(event_type, payload, source_timestamp))

        _, timestamps = self._readings_control.get_first_n_readings(self._batch_size)

        ret = [
            _process_event(
                ('gui', 'system', 'timeseries', 'forecast'), {
                    'timestamp': t,
                    'value': v
                })
            for v, t in zip(event.payload.data['result'], timestamps)]

        self._readings_control.remove_first_n_readings(self._batch_size)
        return ret

    def process_reading(self, event):

        self.send_message(["MultiOutputSVR", "linear", "constant"], 'supported_models')

        self._readings_control.append(event.payload.data["value"], event.payload.data["timestamp"])

        if self._readings_control.size >= self._batch_size + 24 and self._current_model_name:
            model_input, _ = self._readings_control.get_first_n_readings(self._batch_size)

            self._async_group.spawn(self._MODELS[self._current_model_name].predict, [model_input.tolist()])


