import asyncio
import logging

import hat.aio
import hat.event.common
import hat.gateway.common
import pandas


mlog = logging.getLogger(__name__)


class AirReading(hat.gateway.common.Device):
    def __init__(self, conf, event_client, event_type_prefix):
        self._async_group = hat.aio.Group()
        self._event_client = event_client
        self._event_type_prefix = event_type_prefix
        self._df = pandas.read_csv(conf["dataset_path"])
        self._async_group.spawn(self._main_loop)

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
                        type=(*self._event_type_prefix, "gateway", "reading"),
                        source_timestamp=hat.event.common.Timestamp(index, 0),
                        payload=hat.event.common.EventPayloadJson(
                            {"timestamp": timestamp, "value": value},
                        ),
                    )
                ]
            )


info = hat.gateway.common.DeviceInfo(type="example", create=AirReading)
