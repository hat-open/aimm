from air_supervision.modules.model.common import ReturnType
from air_supervision.modules.model import anomaly
from air_supervision.modules.model import forecast


def factory(model_type, model_name, module):
    if model_type == 'anomaly':
        cls = {'SVM': anomaly.SVM,
               'Cluster': anomaly.Cluster,
               'Forest': anomaly.Forest,
               'Forest2': anomaly.Forest2}[model_name]
        return cls(module, model_name)
    elif model_type == 'forecast':
        cls = {'MultiOutputSVR': forecast.MultiOutputSVR,
               'Linear': forecast.Linear,
               'Constant': forecast.Constant}[model_name]
        return cls(module, model_name)
    else:
        raise ValueError(f'incorrect model type {model_type}')


__all__ = ['ReturnType',
           'factory']
