from air_supervision.modules.controller.common import (
    GenericReadingsModule,
    ReadingsModuleBuilder,
)
import logging

mlog = logging.getLogger(__name__)
json_schema_id = None
json_schema_repo = None


async def create(conf, engine, source):
    builder = ReadingsModuleBuilder()

    builder.source = source

    builder.user_action_type = ("user_action", "forecast", "*")
    builder.engine = engine

    builder.model_family = "forecast"
    builder.supported_models = ["MultiOutputSVR", "linear", "constant"]
    builder.batch_size = 48
    builder.min_readings = 24

    return ForecastModule(builder)


class ForecastModule(GenericReadingsModule):
    def transform_row(self, value, timestamp):
        return value
