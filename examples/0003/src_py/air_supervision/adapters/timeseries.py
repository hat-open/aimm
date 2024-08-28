from datetime import datetime, timedelta
import hat.aio
import hat.event.common
import hat.gui.common
import hat.util
import logging


mlog = logging.getLogger(__name__)


async def create_subscription(conf):
    return hat.event.common.create_subscription(
        [("gui", "system", "timeseries", "*"), ("gui", "log", "*")]
    )


async def create_adapter(conf, event_client):
    adapter = Adapter()

    adapter._async_group = hat.aio.Group()
    adapter._event_client = event_client
    adapter._session = set()

    adapter._info = {"anomaly": {}, "forecast": {}}
    adapter._series_values = {"reading": [], "anomaly": [], "forecast": []}
    adapter._series_timestamps = {"reading": [], "anomaly": [], "forecast": []}

    adapter._state_change_cb_registry = hat.util.CallbackRegistry()
    return adapter


info = hat.gui.common.AdapterInfo(
    create_subscription=create_subscription, create_adapter=create_adapter
)


class Adapter(hat.gui.common.Adapter):
    @property
    def async_group(self):
        return self._async_group

    async def create_session(self, user, roles, state, notify_cb):
        session = Session(
            self, state, notify_cb, self._async_group.create_subgroup()
        )
        self._state_change_cb_registry.register(session._on_state_change)
        session._on_state_change()
        return session

    def truncate_lists(self, vals, tss):
        """
        Truncates lists vals and tss so that timestamps don't repeat.
        For example:
        vals = [20,21,25,23,28,19,22,26,21]
        tss  = [1,2,3,4,5,3,4,5,6]

        will be truncated to:
        vals = [20, 21, 25, 23, 28, 21]
        tss  = [1, 2, 3, 4, 5, 6]
        """

        max_ts = tss[0]
        index = 0
        for ts in tss:
            if ts >= max_ts:
                max_ts = ts
                index = index + 1
            else:
                break

        # index of element with value equal to max_ts
        index_last = len(tss) - list(reversed(tss)).index(max_ts)

        # delete elements from index_first to index
        vals_new = vals[:index] + vals[index_last:]
        tss_new = tss[:index] + tss[index_last:]

        return vals_new, tss_new

    async def process_events(self, events):
        for event in events:
            if event.type[1] == "log":
                """
                Additional data for GUI. Just pass it through, JS will handle
                it.
                """

                self._info[event.type[2]] = dict(
                    self._info[event.type[2]],
                    **{event.type[3]: event.payload.data}
                )

            else:
                """
                # Data is from reading OR forecast OR anomaly

                Data has the following structure:
                {
                    'timestamp': datetime.datetime(...),
                    'value': original y value,
                    'result': result from model
                }

                Anomaly:
                    'result' is a number 0 or 1, save 'value' if 'result' == 1
                Forecast:
                    'result' is a predicted value y,always save 'value'
                Reading:
                    'result' DOESN'T EXIST
                """

                series_id = event.type[-1]

                timestamp = datetime.strptime(
                    event.payload.data["timestamp"], "%Y-%m-%d %H:%M:%S"
                )

                if series_id == "anomaly":
                    value = event.payload.data["value"]
                    if event.payload.data["result"] <= 0:
                        continue
                elif series_id == "reading":
                    value = event.payload.data["value"]
                else:
                    value = event.payload.data["result"]

                self._series_values = dict(
                    self._series_values,
                    **{series_id: self._series_values[series_id] + [value]}
                )
                series_t = self._series_timestamps[series_id]
                self._series_timestamps = dict(
                    self._series_timestamps,
                    **{series_id: series_t + [timestamp]}
                )

            reading_v = self._series_values["reading"]
            reading_t = self._series_timestamps["reading"]
            forecast_v = self._series_values["forecast"]
            forecast_t = self._series_timestamps["forecast"]
            anomaly_v = self._series_values["anomaly"]
            anomaly_t = self._series_timestamps["anomaly"]

            reading_v = reading_v[-71:]
            reading_t = reading_t[-71:]
            anomaly_v = anomaly_v[-20:]
            anomaly_t = anomaly_t[-20:]

            if forecast_t:
                forecast_v, forecast_t = self.truncate_lists(
                    forecast_v, forecast_t
                )

                oldest_forecast = max(reading_t) - timedelta(days=2)
                if min(forecast_t) < oldest_forecast:
                    forecast_t = [
                        i for i in forecast_t if i >= oldest_forecast
                    ]
                    forecast_v = forecast_v[-len(forecast_t) :]

                self._series_values["forecast"] = forecast_v
                self._series_timestamps["forecast"] = forecast_t

            self._series_values["reading"] = reading_v
            self._series_timestamps["reading"] = reading_t
            self._series_values["forecast"] = forecast_v
            self._series_timestamps["forecast"] = forecast_t
            self._series_values["anomaly"] = anomaly_v
            self._series_timestamps["anomaly"] = anomaly_t

            self._state_change_cb_registry.notify()


class Session(hat.gui.common.AdapterSession):
    def __init__(self, adapter, state, notify_cb, group):
        self._adapter = adapter
        self._state = state
        self._notify_cb = notify_cb
        self._async_group = group

    async def process_request(self, name, data):
        """Refreshes state dictionary and loops through events
        Adapter received from JS. If such events exist,
        adapter passes them to the Module (creates new events for Module
        component).
        """
        event_type = {
            "setting_change": ("user_action", data["type"], "setting_change"),
            "model_change": ("user_action", data["type"], "model_change"),
        }[data["action"]]
        event = hat.event.common.RegisterEvent(
            type=event_type,
            source_timestamp=None,
            payload=hat.event.common.EventPayloadJson(
                data=data,
            ),
        )
        await self._adapter._event_client.register(([event]))

    @property
    def async_group(self):
        return self._async_group

    def _on_state_change(self):
        self._state.set(
            [],
            {
                "values": self._adapter._series_values,
                "timestamps": {
                    "reading": [
                        str(ts)
                        for ts in self._adapter._series_timestamps["reading"]
                    ],
                    "anomaly": [
                        str(ts)
                        for ts in self._adapter._series_timestamps["anomaly"]
                    ],
                    "forecast": [
                        str(ts)
                        for ts in self._adapter._series_timestamps["forecast"]
                    ],
                },
                "info": {
                    "anomaly": self._adapter._info["anomaly"],
                    "forecast": self._adapter._info["forecast"],
                },
            },
        )
