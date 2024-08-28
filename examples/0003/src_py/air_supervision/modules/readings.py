import hat.aio
import hat.event.common


async def create(conf, engine, source):
    module = ReadingsModule()

    module._source = source
    module._subscription = hat.event.common.create_subscription(
        [("gateway", "example", "?", "gateway", "reading")]
    )
    module._async_group = hat.aio.Group()
    module._engine = engine

    return module


info = hat.event.common.ModuleInfo(create=create)


class ReadingsModule(hat.event.common.Module):
    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def process(self, source, event):
        return [
            hat.event.common.RegisterEvent(
                type=("gui", "system", "timeseries", "reading"),
                source_timestamp=event.source_timestamp,
                payload=event.payload,
            )
        ]
