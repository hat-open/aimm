from air_supervision.modules.controller.model.common import ReturnType
from air_supervision.modules.controller.model import anomaly, forecast


_type_prefix = "air_supervision.aimm"
_anomaly_prefix = f"{_type_prefix}.anomaly"
_forecast_prefix = f"{_type_prefix}.forecast"


def factory(model_type, model_name, module):
    if model_type == "anomaly":
        params = {
            "SVM": {"contamination": 0.3, "svm1": 1, "svm2": 2},
            "Cluster": {"contamination": 0.3, "cluster1": 1, "cluster2": 3},
            "Forest": {"contamination": 0.3, "other_test_p": 1, "third": 4},
            "Forest2": {"contamination2": 0.3, "other_test_p": 1, "third": 4},
        }[model_name]
        return anomaly.AnomalyModel(
            module, f"{_anomaly_prefix}.{model_name}", params
        )
    elif model_type == "forecast":
        params = {
            "MultiOutputSVR": {"C": 2000, "svm1": 1, "svm2": 2},
            "Linear": {"contamination": 0.3, "cluster1": 1, "cluster2": 3},
            "Constant": {"contamination2": 0.3, "other_test_p": 1, "third": 4},
        }[model_name]
        return forecast.ForecastModel(
            module, f"{_forecast_prefix}.{model_name}", params
        )
    else:
        raise ValueError(f"incorrect model type {model_type}")


__all__ = ["ReturnType", "factory"]
