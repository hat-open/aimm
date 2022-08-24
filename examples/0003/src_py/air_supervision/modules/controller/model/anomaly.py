from air_supervision.modules.controller.model.common import (GenericModel,
                                                             ReturnType)
from datetime import datetime
from hat import aio
import csv


class AnomalyModel(GenericModel):

    def __init__(self, module, model_type, hyperparameters):
        super().__init__(module, model_type, hyperparameters)
        self._executor = aio.create_executor()

    async def fit(self, **kwargs):
        if not self._id:
            return
        event_type = ('aimm', 'fit', self._id)

        train_data = await self._executor(self._ext_get_dataset)
        data = {'args': [train_data, None], 'kwargs': kwargs}
        await self._register_event(event_type, data, ReturnType.FIT)

    def _ext_get_dataset(self):
        train_data = []

        with open("dataset/ambient_temperature_system_failure.csv", "r") as f:
            reader = csv.reader(f, delimiter="\t")
            for i, line in enumerate(reader):
                if not i:
                    continue
                timestamp = datetime.strptime(line[0].split(',')[0],
                                              '%Y-%m-%d %H:%M:%S')
                value = float(line[0].split(',')[1])

                value = (float(value) - 32) * 5 / 9

                train_data.append([
                    value,
                    timestamp.hour,
                    int((timestamp.hour >= 7) & (timestamp.hour <= 22)),
                    timestamp.weekday(),
                    int(timestamp.weekday() < 5)])

        return train_data
