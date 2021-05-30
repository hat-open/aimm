import abc
from hat import aio
import hat.event.client
import hat.event.common
import typing

from aimm.common import *  # NOQA


CreateSubscription: typing.Type = typing.NewType(
    'CreateSubscription',
    typing.Callable[typing.Dict, hat.event.common.Subscription])
CreateSubscription.__doc__ = """
Type of the ``create_subscription`` function that the dynamically imported
controls and backends may implement. Receives component configuration as the
only argument and returns a subscription object.
"""


class ProxyClient:
    """Event client proxy

    Args:
        client: concrete client instance
        subscription: event types proxy subscribes to"""

    def __init__(self, client: hat.event.client.Client,
                 subscription: hat.event.common.Subscription):
        self._subscription = subscription
        self._queue = aio.Queue()
        self._client = client

    @property
    def subscription(self) -> hat.event.common.Subscription:
        """event types the proxy subscribes to"""
        return self._subscription

    def notify(self, events: typing.List[hat.event.common.Event]):
        """Informs proxy of newly received events.

        Args:
            events: incoming events"""
        self._queue.put_nowait(events)

    async def receive(self) -> typing.List[hat.event.common.Event]:
        """Receives notified events.

        Returns:
            received events"""
        return await self._queue.get()

    def register(self, events: typing.List[hat.event.common.RegisterEvent]):
        """Bulk-registers a group of new events without waiting for the
        registration to complete.

        Args:
            events: outgoing events"""
        self._client.register(events)

    async def register_with_response(
            self,
            events: typing.List[hat.event.common.RegisterEvent]
            ) -> typing.List[hat.event.common.Event]:
        """Bulk-registers a group of new events and awaits until the
        registration is complete.

        Args:
            events: outgoing events

        Returns:
            registered events"""
        return await self._client.register_with_response(events)

    async def query(self,
                    query_data: hat.event.common.QueryData
                    ) -> typing.List[hat.event.common.Event]:
        """Queries events with given query_data

        Args:
            query_data: query data

        Returns:
            registered events"""
        return await self._client.query(query_data)


class Model(typing.NamedTuple):
    """Server's representation of objects returned by
    :func:`plugins.exec_instantiate`. Contains all metadata neccessary to
    identify and perform other actions with it."""

    instance: typing.Any
    """instance"""
    model_type: str
    """model type, used to identify which plugin to use"""
    instance_id: int
    """instance id"""


class DataAccess(typing.NamedTuple):
    """Representation of a :func:`plugins.exec_data_access` call. May be passed
    as an argument in some methods, indicating that data needs to be retrieved
    prior to calling the main action. See more details on the exact method
    docstrings."""

    name: str
    """name of the data acces type, used to identify which plugin to use"""
    args: typing.Iterable
    """positional arguments to be passed to the plugin call"""
    kwargs: typing.Dict[str, typing.Any]
    """keyword arguments to be passed to the plugin call"""


def backend_create(conf: typing.Dict,
                   group: aio.Group,
                   event_client: typing.Optional['ProxyClient'] = None
                   ) -> 'Backend':
    """Placeholder of the backend's create function, needs to satisfy the given
    signature

    Args:
        conf: backend configuration
        group: async group
        event_client: event client

    Returns:
        backend instance"""


def backend_create_subscription(
        conf: typing.Any) -> hat.event.common.Subscription:
    """Placeholder of the backends optional create subscription function, needs
    to satisfy the given signature

    Args:
        conf: backend configuration

    Returns:
        hat-event subscription"""


class Backend(aio.Resource, abc.ABC):

    """Backend interface. In order to integrate in the aimm server, create a
    module with the implementation and function ``create`` that creates a
    backend instance. The function should have a signature as the
    :func:`backend_create` function.

    The ``event_client`` argument is not ``None`` if backend module also
    contains function named ``create_subscription`` with the same signature as
    the :func:`backend_create_subscription`. The function receives the same
    backend configuration the ``create`` function would receive and returns the
    subscription object for the backend.
    """

    @abc.abstractmethod
    async def get_models(self) -> typing.List[Model]:
        """Get all persisted models, requries that a deserialization function
        is defined for all persisted types

        Returns:
            persisted models"""

    @abc.abstractmethod
    async def create_model(self, model: Model):
        """Store a new model, requires that a serialization for the model type
        is defined

        Args:
            model: model that needs to be persisted"""

    @abc.abstractmethod
    async def update_model(self, model: Model):
        """Replaces the old stored model with the new one, requires that a
        serialization is defined for the model type

        Args:
            model: instance and metadata of the new model"""


def control_create(conf: typing.Dict,
                   engine: 'aimm.server.engine.Engine',  # NOQA
                   group: aio.Group,
                   event_client: typing.Optional['ProxyClient'] = None
                   ) -> 'Control':
    """Placeholder of the control's create function, needs to satisfy the given
    signature

    Args:
        conf: control configuration
        engine: aimm engine
        group: async group
        event_client: event client

    Returns:
        control instance"""


def control_create_subscription(
        conf: typing.Any) -> hat.event.common.Subscription:
    """Placeholder of the controls optional create subscription function, needs
    to satisfy the given signature

    Args:
        conf: control configuration

    Returns:
        hat-event subscriptions"""


class Control(aio.Resource):

    """Control interface. In order to integrate in the aimm server, create a
    module with the implementation and function ``create`` that creates a
    control instance and should have a signature as the :func:`control_create`
    function.

    The ``event_client`` argument is not ``None`` if control module also
    contains function named ``create_subscription`` with the same signature as
    the :func:`control_create_subscription`.  The function receives the same
    control configuration the ``create`` function would receive and returns the
    list of subscriptions ``ProxyClient`` should subscribe to.
    """
