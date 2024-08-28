import asyncio
import logging

import hat.aio
import hat.event.common
import hat.gateway.common
import pandas


mlog = logging.getLogger(__name__)


async def create(conf, event_client, event_type_prefix):
    device = AirReading()

    device._async_group = hat.aio.Group()
    device._event_client = event_client
    device._event_type_prefix = event_type_prefix
    device._df = pandas.read_csv(conf["dataset_path"])
    device._async_group.spawn(device._main_loop)

    return device


info = hat.gateway.common.DeviceInfo(type="example", create=create)


class AirReading(hat.gateway.common.Device):
    @property
    def async_group(self):
        return self._async_group

    async def process_events(self, events):
        pass

    async def _main_loop(self):
        column = "value"
        for index, value in self._df[column].items():
            await asyncio.sleep(0.5)

            timestamp = self._df.iloc[index]["timestamp"]
            value = (float(value) - 32) * 5 / 9

            await self._event_client.register(
                [
                    hat.event.common.RegisterEvent(
                        type=(
                            *self._event_type_prefix,
                            "gateway",
                            "reading",
                        ),
                        source_timestamp=hat.event.common.Timestamp(index, 0),
                        payload=hat.event.common.EventPayloadJson(
                            {"timestamp": timestamp, "value": value},
                        ),
                    )
                ]
            )
