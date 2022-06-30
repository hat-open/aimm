from hat import aio
from hat import util

from aimm.server import common


def create(conf, _):
    backend = DummyBackend()
    backend._group = aio.Group()
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

    def register_model_change_cb(self, cb):
        return util.RegisterCallbackHandle()
