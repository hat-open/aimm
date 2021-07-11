from hat import aio

from aimm.server import common


def create(conf, group, _):
    backend = DummyBackend()
    backend._group = group
    return backend


class DummyBackend(common.Backend):

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._group

    async def get_models(self):
        return []

    async def create_model(self, model):
        return

    async def update_model(self, model):
        return
