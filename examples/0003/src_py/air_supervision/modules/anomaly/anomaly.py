import hat.aio
import hat.event.server.common
from datetime import datetime

from air_supervision.modules.controller_generic import (GenericReadingsModule,
                                                        ReadingsHandler)
import logging

mlog = logging.getLogger(__name__)
json_schema_id = None
json_schema_repo = None
_source_id = 0


async def create(conf, engine):
    module = AnomalyModule()

    global _source_id
    module._source = hat.event.server.common.Source(
        type=hat.event.server.common.SourceType.MODULE,
        name=__name__,
        id=_source_id)
    _source_id += 1

    module._subscription = hat.event.server.common.Subscription([
        ('aimm', '*'),
        ('gui', 'system', 'timeseries', 'reading'),
        ('back_action', 'anomaly', '*')])
    module._async_group = hat.aio.Group()
    module._engine = engine

    module._model_type = 'anomaly'
    module._import_module_name = "{}.{}.{}_model".format(
        __name__, module._model_type, module._model_type)
    module._supported_models = ["Forest", "SVM", "Cluster"]
    module._readings_control = ReadingsHandler()
    module._batch_size = 5

    module.vars = {
        "supported_models": module._supported_models,
        "model_type": module._model_type,
        "import_module_name": module._import_module_name
    }
    return module


class AnomalyModule(GenericReadingsModule):
    def transform_row(self, value, timestamp):
        d = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

        return [float(value),
                d.hour,
                int((d.hour >= 7) & (d.hour <= 22)),
                d.weekday(),
                int(d.weekday() < 5)]
