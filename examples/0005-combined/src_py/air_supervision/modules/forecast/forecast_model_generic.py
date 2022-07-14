from abc import ABC, abstractmethod
import pandas
import numpy
import hat.aio
import hat.event.server.common
from enum import Enum
from air_supervision.modules.model_generic import GenericModel,RETURN_TYPE


class GenericForecastModel(GenericModel):

    def __init__(self, module, name):
        super().__init__(module, name, 'forecast')

    # @abstractmethod
    async def fit(self, **kwargs):

        if self._id:
            x, y = self._get_dataset()
            event_type = ('aimm', 'fit', self._id)
            data = {'args': [x.tolist(), y.tolist()], 'kwargs': kwargs}
            #
            # train_data = self._get_dataset()
            #
            # event_type = ('aimm', 'fit', self._id)
            #
            # data = {'args': [train_data, None], 'kwargs': kwargs}



            await self._register_event(event_type, data, RETURN_TYPE.F_FIT)


    def _get_dataset(self):

        import csv
        from datetime import datetime

        values = []

        with open("dataset/ambient_temperature_system_failure.csv", "r") as f:
            reader = csv.reader(f, delimiter="\t")
            for i, line in enumerate(reader):
                if not i:
                    continue
                timestamp = datetime.strptime(line[0].split(',')[0], '%Y-%m-%d %H:%M:%S')
                value = float(line[0].split(',')[1])
                value = (float(value) - 32) * 5 / 9

                values.append(value)

        x, y = [], []
        for i in range(48, len(values) - 24, 24):
            x.append(values[i - 48:i])
            y.append(values[i:i + 24])

        x, y = numpy.array(x), numpy.array(y)

        return x, y
