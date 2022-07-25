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
from air_supervision.modules.forecast.forecast_model_generic import RETURN_TYPE
import numpy as np
from air_supervision.modules.controller_generic import GenericReadingsModule, ReadingsHandler,_register_event
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

    module._model_type = 'forecast'
    module._import_module_name = f"air_supervision.modules.{module._model_type}.{module._model_type}_model"
    module._supported_models = ["MultiOutputSVR", "linear", "constant"]
    module.readings_control = ReadingsHandler()
    module._batch_size = 48

    module.vars = {
        "supported_models": module._supported_models,
        "model_type": module._model_type,
        "import_module_name": module._import_module_name
    }

    return module


class ForecastModule(GenericReadingsModule):

    def transform_row(self, value, timestamp):
        return value
