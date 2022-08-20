import hat.aio
import hat.event.server.common
from air_supervision.modules.controller_generic import GenericReadingsModule
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
        ('user_action', 'forecast', '*')])
    module._async_group = hat.aio.Group()
    module._engine = engine

    module._model_type = 'forecast'
    module._import_module_name = f"{__name__}_model"
    module._supported_models = ["MultiOutputSVR", "linear", "constant"]
    module._batch_size = 48

    module.vars = {"supported_models": module._supported_models,
                   "model_type": module._model_type,
                   "import_module_name": module._import_module_name}

    return module


class ForecastModule(GenericReadingsModule):

    def transform_row(self, value, timestamp):
        return value
