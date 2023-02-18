from air_supervision.modules.controller.model.common import (
    GenericModel,
    ReturnType,
    request_id_counter,
)
from hat import aio
import csv
import numpy
import logging


mlog = logging.getLogger(__name__)


class ForecastModel(GenericModel):
    def __init__(self, module, model_type, hyperparameters):
        super().__init__(module, model_type, hyperparameters)
        self._executor = aio.create_executor()

    async def fit(self, **kwargs):
        if not self._id:
            return
        event_type = ("aimm", "fit", self._id)

        x, y = await self._executor(self._ext_get_dataset)
        data = {
            "args": [x.tolist(), y.tolist()],
            "kwargs": kwargs,
            "request_id": str(next(request_id_counter)),
        }
        await self._register_event(event_type, data, ReturnType.FIT)

    def _ext_get_dataset(self):
        values = []

        with open("dataset/ambient_temperature_system_failure.csv", "r") as f:
            reader = csv.reader(f, delimiter="\t")
            for i, line in enumerate(reader):
                if not i:
                    continue
                value = float(line[0].split(",")[1])
                value = (float(value) - 32) * 5 / 9

                values.append(value)

        x, y = [], []
        for i in range(48, len(values) - 24, 24):
            x.append(values[i - 48 : i])
            y.append(values[i : i + 24])

        x, y = numpy.array(x), numpy.array(y)

        fit_start = int(len(x) * 0.25)
        return x[fit_start:], y[fit_start:]
