import hat.aio
import hat.event.common
import hat.gui.common
import hat.util
import asyncio
import sys
from datetime import datetime
json_schema_id = None
json_schema_repo = None


async def create_subscription(conf):
    return hat.event.common.Subscription([
        ('gui', 'system', 'timeseries', '*'),
        ('gui', 'log', '*')
    ])


async def create_adapter(conf, event_client):
    adapter = Adapter()

    adapter._async_group = hat.aio.Group()
    adapter._event_client = event_client
    adapter._session = set()

    adapter._info = {}
    adapter._series_values = {
        'reading': [],
        'forecast': []}
    adapter._series_timestamps = {
        'reading': [],
        'forecast': []}

    adapter._state_change_cb_registry = hat.util.CallbackRegistry()
    try:
        adapter._async_group.spawn(adapter._main_loop)
    except:
        pass
    return adapter


class Adapter(hat.gui.common.Adapter):

    @property
    def async_group(self):
        return self._async_group

    async def create_session(self, juggler_client):
        self._session = Session(self,
                                juggler_client,
                                self._async_group.create_subgroup())
        # self._sessions.add(session)
        return self._session

    def subscribe_to_state_change(self, callback):
        return self._state_change_cb_registry.register(callback)

    async def _main_loop(self):
        while True:

            try:
                events = await self._event_client.receive()
            except:
                pass
            for event in events:
                if event.event_type[1] == 'log':
                    # self._info[event.event_type[2]] = event.payload.data

                    self._info = dict(self._info, **{event.event_type[2]: event.payload.data})

                else:  # reading or forecast

                    series_id = event.event_type[-1]
                    timestamp = datetime.strptime(event.payload.data['timestamp'], '%Y-%m-%d %H:%M:%S')
                    value = event.payload.data['value']

                    if series_id == 'forecast':
                        if event.payload.data['is_anomaly'] <= 0:
                            continue

                    self._series_values = dict(self._series_values,
                                               **{series_id: self._series_values[series_id] + [value]})
                    self._series_timestamps = dict(self._series_timestamps,
                                                   **{series_id: self._series_timestamps[series_id] + [timestamp]})

            if len(self._series_values['reading']) > 71:
                self._series_values['reading'].pop(0)
                self._series_timestamps['reading'].pop(0)

                m = min(self._series_timestamps['reading'])

                self._series_values['forecast'] = [f for f in self._series_values['forecast']]

                sorted__forecast_ts = sorted(self._series_timestamps['forecast'])
                sorted_forcast = [x for _, x in sorted(zip(self._series_timestamps['forecast'], self._series_values['forecast']))]

                self._series_timestamps['forecast'] = [i for i in sorted__forecast_ts if i >= m]
                self._series_values['forecast'] = sorted_forcast[-len(self._series_timestamps['forecast']):]

            if self._session:
                self._session._on_state_change()
            self._state_change_cb_registry.notify()


class Session(hat.gui.common.AdapterSession):

    def __init__(self, adapter, juggler_client, group):
        self._adapter = adapter
        self._juggler_client = juggler_client
        self._async_group = group
        try:
            self._async_group.spawn(self._run)
        except:
            pass

    async def _run(self):
        """This function is periodically triggered on state change.
        It refreshes state dictionary and loops through events
        Adapter received from JS.If such events exist,
        adapter passes them to the Module (creates new events for Module
        component).
        """

        try:
            self._on_state_change()
            with self._adapter.subscribe_to_state_change(
                    self._on_state_change):
                while True:
                    data = await self._juggler_client.receive()  # sent data
                    # print("CB..")

                    if data['action'] == 'setting_change':
                        event_type = ('back_action', 'setting_change')
                    elif data['action'] == 'model_change':
                        event_type = ('back_action', 'model_change')
                    # sending data to module 'module'
                    self._adapter._event_client.register(([
                        hat.event.common.RegisterEvent(
                            event_type=event_type,
                            source_timestamp=None,
                            payload=hat.event.common.EventPayload(
                                type=hat.event.common.EventPayloadType.JSON,
                                data=data))]))
        except AttributeError:
            # breakpoint()
            await self.wait_closing()

        except asyncio.exceptions.CancelledError:
            print("Unexpected closing:", sys.exc_info()[0])
            await self.wait_closing()

    @property
    def async_group(self):
        return self._async_group

    def _on_state_change(self):


        self._juggler_client.set_local_data({
            'values': self._adapter._series_values,
            'timestamps': {
                'reading': [str(ts) for ts in self._adapter._series_timestamps['reading']],
                'forecast': [str(ts) for ts in self._adapter._series_timestamps['forecast']],
            },
            'info': self._adapter._info
        })
