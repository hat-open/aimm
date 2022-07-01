import pandapower.estimation
import pandapower.networks
import time

from aimm import plugins


@plugins.model
class StateEstimator(plugins.Model):

    def __init__(self):
        pass

    def fit(self):
        pass

    def predict(self, measurements):
        network = pandapower.networks.case14()
        pandapower.create.create_measurement(network, 'v', 'bus', 1, 0.05, 0)
        for measurement in measurements:
            pandapower.create.create_measurement(
                network,
                measurement['type'], measurement['element_type'],
                measurement['value'], measurement['std_dev'],
                measurement['element'], side=measurement.get('side'))

        pandapower.estimation.estimate(network)
        time.sleep(0.5)
        return network.res_bus_est.to_dict()

    def serialize(self):
        return bytes()

    @classmethod
    def deserialize(cls, instance_bytes):
        return StateEstimator()
