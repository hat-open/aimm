import hat.aio
import hat.event.server.common
import sys
import numpy as np
from datetime import datetime
sys.path.insert(0, '../../')
import importlib
from air_supervision.modules.anomaly.model_controller_generic import RETURN_TYPE
from air_supervision.modules.model_controller import ReadingsModule, ReadingsControl,_register_event
import logging

mlog = logging.getLogger(__name__)
json_schema_id = None
json_schema_repo = None
_source_id = 0


# class PREDICTION_STATUS(Enum):
#     NOT_FITTED_YET = 0
#     ACQUIRING_DATA = 1
#     SENDING = 2

async def create(conf, engine):
    module = AnomalyModule()

    global _source_id
    module._source = hat.event.server.common.Source(
        type=hat.event.server.common.SourceType.MODULE,
        name=__name__,
        id=_source_id)
    _source_id += 1

    module._subscription = hat.event.server.common.Subscription([
        ('aimm', '*'),
        ('gui', 'system', 'timeseries', 'reading'),
        ('back_action', 'anomaly', '*')])
    module._async_group = hat.aio.Group()
    module._engine = engine

    module._model_ids = {}
    module._current_model_name = None

    module._predictions = []
    module._predictions_times = []


    module.data_tracker = 0


    module._model_type = 'anomaly'
    module._import_module_name = "air_supervision.modules.anomaly.model_controller"
    module._supported_models = ["Forest", "SVM", "Cluster"]
    module._readings_control = ReadingsControl()
    module._MODELS = {}
    module._request_ids = {}
    module._batch_size = 48

    return module


class AnomalyModule(ReadingsModule):
    def process_predict(self, event):

        def _process_event(event_type, payload, source_timestamp=None):
            return self._engine.create_process_event(
                self._source,
                _register_event(event_type, payload, source_timestamp))

        vals = np.array(self._predictions[-5:])[:, 0]
        org_vals_from_aimm = np.array(event.payload.data['result'])[:, 0]

        results = np.array(event.payload.data['result'])[:, -1]

        rez = [
            _process_event(
                ('gui', 'system', 'timeseries', 'anomaly'), {
                    'timestamp': t,
                    'is_anomaly': r,
                    'value': v
                })
            for r, t, v in zip(results, self._predictions_times[-5:], vals)]

        self._predictions_times = self._predictions_times[-5:]
        self._predictions = self._predictions[-5:]
        return rez

    def process_reading(self, event):
        self.send_message(["Forest", "SVM", "Cluster"], 'supported_models')

        if self._current_model_name:
            d = datetime.strptime(event.payload.data['timestamp'], '%Y-%m-%d %H:%M:%S')
            predict_row = [float(event.payload.data['value']),
                           d.hour,
                           int((d.hour >= 7) & (d.hour <= 22)),
                           d.weekday(),
                           int(d.weekday() < 5)]

            self._predictions_times.append(str(d))
            self._predictions.append(predict_row)

            self.data_tracker += 1
            if self.data_tracker >= 5:

                try:
                    self._async_group.spawn(
                        self._MODELS[self._current_model_name].predict, np.array(self._predictions[-5:]))
                except:
                    pass
                self.data_tracker = 0
