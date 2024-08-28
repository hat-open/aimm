from hat import aio
from hat import util
from typing import Any, Dict, Callable, Iterable, List, NamedTuple, Optional
import abc
import hat.event.eventer.client
import hat.event.common

from aimm.common import *  # NOQA


CreateSubscription = Callable[[Dict], hat.event.common.Subscription]
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

    def __init__(
        self,
        client: hat.event.eventer.client.Client,
        subscription: hat.event.common.Subscription,
    ):
        self._subscription = subscription
        self._queue = aio.Queue()
        self._client = client
        self._group = aio.Group()

    @property
    def subscription(self) -> hat.event.common.Subscription:
        """event types the proxy subscribes to"""
        return self._subscription

    def notify(self, events: List[hat.event.common.Event]):
        """Informs proxy of newly received events."""
        self._queue.put_nowait(events)

    async def receive(self) -> List[hat.event.common.Event]:
        """Receives notified events."""
        return await self._queue.get()

    def register(self, events: List[hat.event.common.RegisterEvent]):
        """Bulk-registers a group of new events without waiting for the
        registration to complete."""
        self._group.spawn(self._client.register, events, False)

    async def register_with_response(
        self, events: List[hat.event.common.RegisterEvent]
    ) -> List[hat.event.common.Event]:
        """Bulk-registers a group of new events and awaits until the
        registration is complete."""
        return await self._client.register(events, with_response=True)

    async def query(
        self, query_data: hat.event.common.QueryParams
    ) -> List[hat.event.common.Event]:
        """Queries events with given query_data"""
        return (await self._client.query(query_data)).events


class Model(NamedTuple):
    """Server's representation of objects returned by
    :func:`plugins.exec_instantiate`. Contains all metadata neccessary to
    identify and perform other actions with it."""

    instance: Any
    """instance"""
    model_type: str
    """model type, used to identify which plugin to use"""
    instance_id: int
    """instance id"""


class DataAccess(NamedTuple):
    """Representation of a :func:`plugins.exec_data_access` call. May be passed
    as an argument in some methods, indicating that data needs to be retrieved
    prior to calling the main action. See more details on the exact method
    docstrings."""

    name: str
    """name of the data acces type, used to identify which plugin to use"""
    args: Iterable
    """positional arguments to be passed to the plugin call"""
    kwargs: Dict[str, Any]
    """keyword arguments to be passed to the plugin call"""


class Engine(aio.Resource, abc.ABC):
    """Engine interface"""

    @abc.abstractproperty
    def state(self) -> Dict:
        """Engine state, contains references to all models and actions. It's
        never modified in-place, instead :meth:`subscribe_to_state_change`
        should be used"""

    @abc.abstractmethod
    def subscribe_to_state_change(
        self, cb: Callable[[], None]
    ) -> util.RegisterCallbackHandle:
        """Subscribes to any changes to the engine state"""

    @abc.abstractmethod
    def create_instance(
        self, model_type: str, *args: Any, **kwargs: Any
    ) -> "Action":
        """Starts an action that creates a model instance and stores it in
        state.

        Args:
            model_type: model type
            *args: instantiation arguments
            **kwargs: instantiation keyword arguments"""

    @abc.abstractmethod
    async def add_instance(self, model_type: str, instance: Any) -> Model:
        """Adds existing instance to the state"""

    @abc.abstractmethod
    async def update_instance(self, model: Model):
        """Update existing instance in the state"""

    @abc.abstractmethod
    async def fit(
        self, instance_id: int, *args: Any, **kwargs: Any
    ) -> "Action":
        """Starts an action that fits an existing model instance. The used
        fitting function is the one assigned to the model type. The instance,
        while it is being fitted, is not accessable by any of the other
        functions that would use it (other calls to fit, predictions, etc.).

        Args:
            instance_id: id of model instance that will be fitted
            *args: arguments to pass to the fitting function - if of type
                :class:`aimm.server.common.DataAccess`, the value passed to the
                fitting function is the result of the call to that plugin,
                other arguments are passed directly
            **kwargs: keyword arguments, work the same as the positional
                arguments"""

    @abc.abstractmethod
    async def predict(
        self, instance_id: int, *args: Any, **kwargs: Any
    ) -> "Action":
        """Starts an action that uses an existing model instance to perform a
        prediction. The used prediction function is the one assigned to model's
        type. The instance, while prediction is called, is not accessable by
        any of the other functions that would use it (other calls to predict,
        fittings, etc.).  If instance has changed while predicting, it is
        updated in the state and database.

        Args:
            instance_id: id of the model instance used for prediction
            *args: arguments to pass to the predict function - if of type
                :class:`aimm.server.common.DataAccess`, the value passed to the
                predict function is the result of the call to that plugin,
                other arguments are passed directly
            **kwargs: keyword arguments, work the same as the positional
                arguments

        Returns:
            Reference to task of the managable predict call, result of it is
            the model's prediction"""


class Action(aio.Resource, abc.ABC):
    """Represents a manageable call. Is an :class:`aio.Resource` so call can be
    cancelled using ``async_close``."""

    @abc.abstractmethod
    async def wait_result(self) -> Any:
        """Wait until call returns a result. May raise
        :class:`asyncio.CancelledError` in case the call was cancelled."""


def create_backend(
    conf: Dict, event_client: Optional["ProxyClient"] = None
) -> "Backend":
    """Placeholder of the backend's create function, needs to satisfy the given
    signature"""


def create_backend_subscription(conf: Any) -> hat.event.common.Subscription:
    """Placeholder of the backends optional create subscription function, needs
    to satisfy the given signature"""


class Backend(aio.Resource):
    """Backend interface. In order to integrate in the aimm server, create a
    module with the implementation and function ``create`` that creates a
    backend instance. The function should have a signature as the
    :func:`create_backend` function.

    The ``event_client`` argument is not ``None`` if backend module also
    contains function named ``create_subscription`` with the same signature as
    the :func:`create_backend_subscription`. The function receives the same
    backend configuration the ``create`` function would receive and returns the
    subscription object for the backend.
    """

    @abc.abstractmethod
    async def get_models(self) -> List[Model]:
        """Get all persisted models, requries that a deserialization function
        is defined for all persisted types

        Returns:
            persisted models"""

    @abc.abstractmethod
    async def create_model(self, model_type: str, instance: Any):
        """Store a new model, requires that a serialization for the model type
        is defined"""

    @abc.abstractmethod
    async def update_model(self, model: Model):
        """Replaces the old stored model with the new one, requires that a
        serialization is defined for the model type"""

    def register_model_change_cb(
        self, cb: Callable[[Model], None]
    ) -> util.RegisterCallbackHandle:
        """Register callback for backend-side model changes. Implementation
        optional, defaults to ignoring the callback."""
        return util.RegisterCallbackHandle(cancel=lambda: None)


def create_control(
    conf: Dict, engine: Engine, event_client: Optional["ProxyClient"] = None
) -> "Control":
    """Placeholder of the control's create function, needs to satisfy the given
    signature"""


def create_control_subscription(conf: Any) -> hat.event.common.Subscription:
    """Placeholder of the controls optional create subscription function, needs
    to satisfy the given signature"""


class Control(aio.Resource):
    """Control interface. In order to integrate in the aimm server, create a
    module with the implementation and function ``create`` that creates a
    control instance and should have a signature as the :func:`create_control`
    function.

    The ``event_client`` argument is not ``None`` if control module also
    contains function named ``create_subscription`` with the same signature as
    the :func:`create_control_subscription`.  The function receives the same
    control configuration the ``create`` function would receive and returns the
    list of subscriptions ``ProxyClient`` should subscribe to.
    """
