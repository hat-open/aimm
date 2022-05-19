import hat.aio
import hat.event.common
import hat.gui.common
import hat.util
import asyncio
import sys

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
    adapter._series = {'reading': [], 'forecast': []}

    adapter._state_change_cb_registry = hat.util.CallbackRegistry()

    adapter._async_group.spawn(adapter._main_loop)

    return adapter


class Adapter(hat.gui.common.Adapter):

    @property
    def async_group(self):
        return self._async_group

    async def create_session(self, juggler_client):
        self._session = Session(self,
            juggler_client,
            self._async_group.create_subgroup())
        #self._sessions.add(session)
        return self._session

    def subscribe_to_state_change(self, callback):
        return self._state_change_cb_registry.register(callback)

    async def _main_loop(self):
        while True:
            events = await self._event_client.receive()
            for event in events:
                if event.event_type[1] == 'log':
                    if event.event_type[2] == 'model_change':
                        if 'model_now' in event.payload.data['kwargs']:
                            self._series['model_before'] = event.payload.data['kwargs']['model_before']
                            self._series['model_now'] = event.payload.data['kwargs']['model_now']

                    if event.event_type[2] in ['model_action', 'model_state']:
                        self._series[event.event_type[2]] = event.payload.data

                else:
                    series_id = event.event_type[-1]
                    new_series = self._series[series_id] + [event.payload.data]
                    self._series = dict(self._series, **{series_id: new_series})

            if len(self._series['reading']) > 71:
                self._series['reading'] = self._series['reading'][-48:]
            if len(self._series['forecast']) > 24:
                self._series['forecast'] = self._series['forecast'][-24:]


            #for session in self._sessions:
            if self._session:
                self._session._on_state_change()
            self._state_change_cb_registry.notify()


class Session(hat.gui.common.AdapterSession):

    def __init__(self,adapter, juggler_client, group):
        self._adapter = adapter
        self._juggler_client = juggler_client
        self._async_group = group
        self._async_group.spawn(self._run)

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
                    #print("CB..")

                    # sending data to module 'module'
                    self._adapter._event_client.register(([
                        hat.event.common.RegisterEvent(
                            event_type=('backValue', 'backValue', 'modelChange'),
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
        self._juggler_client.set_local_data(self._adapter._series)
