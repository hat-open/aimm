from hat import aio
import itertools

from aimm.server import common


def create(conf, _):
    backend = DummyBackend()
    backend._group = aio.Group()
    backend._id_counter = itertools.count(1)
    return backend


class DummyBackend(common.Backend):
    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._group

    async def get_models(self):
        return []

    async def create_model(self, model_type, instance):
        return common.Model(
            model_type=model_type,
            instance=instance,
            instance_id=next(self._id_counter),
        )

    async def update_model(self, model):
        return
