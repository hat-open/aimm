from hat.event.server import common
import hat.aio
import logging


mlog = logging.getLogger(__name__)


json_schema_id = None
json_schema_repo = None

_source_id = 0


async def create(conf, engine):
    module = EnableAll()

    global _source_id
    module._source = common.Source(
        type=common.SourceType.MODULE,
        name=__name__,
        id=_source_id)
    _source_id += 1

    module._subscription = common.Subscription([
        ('gateway', '?', '?', '?', 'gateway', 'running')])
    module._async_group = hat.aio.Group()
    module._engine = engine

    return module


class EnableAll(common.Module):

    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def create_session(self):
        return EnableSession(self._engine, self._async_group.create_subgroup(),
                             self._source)


class EnableSession(common.ModuleSession):

    def __init__(self, engine, group, source):
        self._engine = engine
        self._async_group = group
        self._source = source

    @property
    def async_group(self):
        return self._async_group

    async def process(self, changes):
        return [self._engine.create_process_event(
            self._source,
            common.RegisterEvent(
                event_type=tuple([*e.event_type[:-2], 'system', 'enable']),
                source_timestamp=None,
                payload=common.EventPayload(type=common.EventPayloadType.JSON,
                                            data=True)))
                for e in changes if e.payload.data is False]
