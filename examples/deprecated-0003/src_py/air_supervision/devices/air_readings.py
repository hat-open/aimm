import asyncio
import hat.aio
import hat.event.common
import hat.gateway.common
import pandas


json_schema_id = None
json_schema_repo = None
device_type = 'example'


async def create(conf, event_client, event_type_prefix):
    device = AirReading()

    device._async_group = hat.aio.Group()
    device._event_client = event_client
    device._event_type_prefix = event_type_prefix
    device._df = pandas.read_csv(conf['dataset_path'])
    device._async_group.spawn(device._main_loop)

    return device


class AirReading(hat.gateway.common.Device):

    @property
    def async_group(self):
        return self._async_group

    async def _main_loop(self):
        column = 'PT08.S1(CO)'
        for index, value in self._df[column].iteritems():
            await asyncio.sleep(0.5)
            self._event_client.register([
                hat.event.common.RegisterEvent(
                    event_type=(*self._event_type_prefix,
                                'gateway', 'reading'),
                    source_timestamp=hat.event.common.Timestamp(index, 0),
                    payload=hat.event.common.EventPayload(
                        type=hat.event.common.EventPayloadType.JSON,
                        data=value))])
