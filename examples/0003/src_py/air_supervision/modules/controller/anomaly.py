from datetime import datetime

from air_supervision.modules.controller.common import (
    GenericReadingsModule,
    ReadingsModuleBuilder,
)
from hat.event import common

import logging

mlog = logging.getLogger(__name__)


async def create(conf, engine, source):
    builder = ReadingsModuleBuilder()

    builder.source = source

    builder.user_action_type = ("user_action", "anomaly", "*")
    builder.engine = engine

    builder.model_family = "anomaly"
    builder.supported_models = ["Forest", "SVM", "Cluster"]
    builder.batch_size = 48
    builder.min_readings = 24

    return AnomalyModule(builder)


info = common.ModuleInfo(create=create)


class AnomalyModule(GenericReadingsModule):
    def transform_row(self, value, timestamp):
        d = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

        return [
            float(value),
            d.hour,
            int((d.hour >= 7) & (d.hour <= 22)),
            d.weekday(),
            int(d.weekday() < 5),
        ]
