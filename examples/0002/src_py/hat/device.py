import logging
import asyncio

from hat import aio
from hat import json
import hat.event.common
import hat.gateway.common

from hat.drivers import iec104


mlog = logging.getLogger(__name__)
json_schema_id = 'hat-aimm://device.yaml#'
json_schema_repo = json.SchemaRepository(json.decode("""
---
id: 'hat-aimm://device.yaml#'
type: object
...
""", format=json.Format.YAML))

device_type = 'device'


async def create(conf, client, event_type_prefix):
    device = Device()
    device._async_group = aio.Group()
    device._event_client = client
    device._async_group.spawn(device._connection_loop)
    return device


class Device(hat.gateway.common.Device):

    @property
    def async_group(self):
        return self._async_group

    async def _connection_loop(self):
        try:
            connection = None
            while True:
                try:
                    connection = await iec104.connect(
                        addr=iec104.Address('127.0.0.1', 20001),
                        interrogate_cb=None,
                        counter_interrogate_cb=None,
                        command_cb=None,
                        response_timeout=10,
                        supervisory_timeout=10,
                        test_timeout=10,
                        send_window_size=10,
                        receive_window_size=10)
                except Exception as e:
                    mlog.error('connect failed %s', e, exc_info=e)
                if not connection or connection.is_closed:
                    await asyncio.sleep(3)
                    continue
                self._conn_group = self._async_group.create_subgroup()
                self._conn_group.spawn(self._receive_loop, connection)
                self._conn_group.spawn(aio.call_on_cancel,
                                       connection.async_close)
                try:
                    await connection.wait_closed()
                finally:
                    connection = None
                    await self._conn_group.async_close()
        finally:
            self._async_group.close()

    async def _receive_loop(self, connection):
        while True:
            data_list = await connection.receive()
            self._event_client.register([_data_to_event(i) for i in data_list])


def _data_to_event(data):
    bus_id = data.asdu_address
    measurement_type = ['p', 'q', 'v', 'va'][data.io_address]
    return hat.event.common.RegisterEvent(
        event_type=(('measurement', str(bus_id), measurement_type)),
        source_timestamp=None,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=data.value.value))
