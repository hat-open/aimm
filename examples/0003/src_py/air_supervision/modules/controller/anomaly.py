import hat.aio
import hat.event.server.common
from datetime import datetime

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

    builder.user_action_type = ('user_action', 'anomaly', '*')
    builder.engine = engine

    builder.model_family = 'anomaly'
    builder.supported_models = ['Forest', 'SVM', 'Cluster']
    builder.batch_size = 48
    builder.min_readings = 24

    return AnomalyModule(builder)


class AnomalyModule(GenericReadingsModule):
    def transform_row(self, value, timestamp):
        d = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

        return [float(value),
                d.hour,
                int((d.hour >= 7) & (d.hour <= 22)),
                d.weekday(),
                int(d.weekday() < 5)]
