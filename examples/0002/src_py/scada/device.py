import logging
import asyncio

from hat import aio
import hat.event.common
import hat.gateway.common

from hat.drivers import iec104
from hat.drivers import tcp


mlog = logging.getLogger(__name__)


class Device(hat.gateway.common.Device):

    def __init__(self, _, client, __):
        self._async_group = aio.Group()
        self._event_client = client
        self._async_group.spawn(self._connection_loop)

    @property
    def async_group(self):
        return self._async_group

    async def process_events(self, events):
        pass

    async def _connection_loop(self):
        try:
            connection = None
            while True:
                try:
                    connection = await iec104.connect(
                        addr=tcp.Address("127.0.0.1", 20001)
                    )
                except Exception as e:
                    mlog.error("connect failed %s", e, exc_info=e)
                if not connection or connection.is_closed:
                    await asyncio.sleep(3)
                    continue
                self._conn_group = self._async_group.create_subgroup()
                self._conn_group.spawn(self._receive_loop, connection)
                self._conn_group.spawn(
                    aio.call_on_cancel, connection.async_close
                )
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
            await self._event_client.register(
                [_data_to_event(i) for i in data_list]
            )


info = hat.gateway.common.DeviceInfo(type="device", create=Device)


def _data_to_event(data):
    bus_id = data.asdu_address
    measurement_type = ["p", "q", "v", "va"][data.io_address]
    return hat.event.common.RegisterEvent(
        type=("measurement", str(bus_id), measurement_type),
        source_timestamp=None,
        payload=hat.event.common.EventPayloadJson(data.data.value),
    )
