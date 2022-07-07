from abc import ABC, abstractmethod

import hat.aio
import hat.event.server.common
import yaml
from enum import Enum
from air_supervision.modules.model_generic import GenericModel


class RETURN_TYPE(Enum):
    PREDICT = 1
    FIT = 2
    CREATE = 3


class GenericAnomalyModel(GenericModel):

    def __init__(self, module, name):
        super().__init__(module, name, 'anomaly')


    # @abstractmethod
    async def fit(self, **kwargs):
        if self._id:
            train_data = self._get_dataset()

            event_type = ('aimm', 'fit', self._id)

            data = {'args': [train_data, None], 'kwargs': kwargs}

            await self._register_event(event_type, data, RETURN_TYPE.FIT)

    def _get_dataset(self):
        import csv
        from datetime import datetime

        train_data = []

        with open("dataset/ambient_temperature_system_failure.csv", "r") as f:
            reader = csv.reader(f, delimiter="\t")
            for i, line in enumerate(reader):
                if not i:
                    continue
                timestamp = datetime.strptime(line[0].split(',')[0], '%Y-%m-%d %H:%M:%S')
                value = float(line[0].split(',')[1])

                value = (float(value) - 32) * 5 / 9



                train_data.append([
                    value,
                    timestamp.hour,
                    int((timestamp.hour >= 7) & (timestamp.hour <= 22)),
                    timestamp.weekday(),
                    int(timestamp.weekday() < 5)
                ])
        return train_data
