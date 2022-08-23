import hat.aio
import hat.event.server.common
from air_supervision.modules.controller.common import (GenericReadingsModule,
                                                       ReadingsModuleBuilder)
import logging

mlog = logging.getLogger(__name__)
json_schema_id = None
json_schema_repo = None
_source_id = 0


async def create(conf, engine):
    builder = ReadingsModuleBuilder()

    global _source_id
    builder.source = hat.event.server.common.Source(
        type=hat.event.server.common.SourceType.MODULE,
        name=__name__,
        id=_source_id)
    _source_id += 1

    builder.user_action_type = ('user_action', 'forecast', '*')
    builder.engine = engine

    builder.model_family = 'forecast'
    builder.supported_models = ['MultiOutputSVR', 'linear', 'constant']
    builder.batch_size = 48
    builder.min_readings = 24

    return ForecastModule(builder)


class ForecastModule(GenericReadingsModule):

    def transform_row(self, value, timestamp):
        return value
