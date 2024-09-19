from datetime import datetime, timedelta
from collections import deque
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


class Adapter(hat.gui.common.Adapter):
    def __init__(self, _, event_client):
        self._async_group = hat.aio.Group()
        self._event_client = event_client
        self._session = set()

        self._models_info = {"anomaly": {}, "forecast": {}}
        self._series_values = {
            "reading": deque(maxlen=72),
            "anomaly": deque(maxlen=21),
            "forecast": []
        }
        self._series_timestamps = {
            "reading": deque(maxlen=72),
            "anomaly": deque(maxlen=21),
            "forecast": []
        }

        self._state_change_cb_registry = hat.util.CallbackRegistry()

    @property
    def async_group(self):
        return self._async_group

    @property
    def series_values(self):
        return self._series_values

    @property
    def series_timestamps(self):
        return self._series_timestamps

    @property
    def models_info(self):
        return self._models_info

    async def create_session(self, user, roles, state, notify_cb):
        session = Session(
            self,
            state,
            notify_cb,
            self._async_group.create_subgroup(),
            self._event_client
        )
        self._state_change_cb_registry.register(session.on_state_change)
        session.on_state_change()
        return session

    async def process_events(self, events):
        for event in events:
            if event.type[1] == "log":
                """
                Additional data for GUI. Just pass it through, JS will handle
                it.
                """

                self._models_info[event.type[2]] = dict(
                    self._models_info[event.type[2]],
                    **{event.type[3]: event.payload.data}
                )
                continue

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
            if series_id == "anomaly" and event.payload.data["result"] <= 0:
                continue
            value_k = "result" if series_id == "forecast" else "value"
            self._series_values[series_id].append(event.payload.data[value_k])

            self._series_timestamps[series_id].append(datetime.strptime(
                event.payload.data["timestamp"], "%Y-%m-%d %H:%M:%S"
            ))

            forecast_v = self._series_values["forecast"]
            forecast_t = self._series_timestamps["forecast"]

            if forecast_t:
                forecast_v, forecast_t = _truncate_lists(
                    forecast_v, forecast_t
                )

                oldest_forecast = (
                    max(self._series_timestamps["reading"]) - timedelta(days=2)
                )
                if min(forecast_t) < oldest_forecast:
                    forecast_t = [
                        i for i in forecast_t if i >= oldest_forecast
                    ]
                    forecast_v = forecast_v[-len(forecast_t) :]

                self._series_values["forecast"] = forecast_v
                self._series_timestamps["forecast"] = forecast_t

        self._state_change_cb_registry.notify()


class Session(hat.gui.common.AdapterSession):
    def __init__(self, adapter, state, notify_cb, group, event_client):
        self._adapter = adapter
        self._state = state
        self._notify_cb = notify_cb
        self._async_group = group
        self._event_client = event_client

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
        await self._event_client.register(([event]))

    @property
    def async_group(self):
        return self._async_group

    def on_state_change(self):
        self._state.set(
            [],
            {
                "values": {
                    k: list(v) for k, v in self._adapter.series_values.items()
                },
                "timestamps": {
                    "reading": [
                        str(ts)
                        for ts in self._adapter.series_timestamps["reading"]
                    ],
                    "anomaly": [
                        str(ts)
                        for ts in self._adapter.series_timestamps["anomaly"]
                    ],
                    "forecast": [
                        str(ts)
                        for ts in self._adapter.series_timestamps["forecast"]
                    ],
                },
                "info": {
                    "anomaly": self._adapter.models_info["anomaly"],
                    "forecast": self._adapter.models_info["forecast"],
                },
            },
        )


def _truncate_lists(vals, tss):
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


info = hat.gui.common.AdapterInfo(
    create_subscription=create_subscription, create_adapter=Adapter
)
