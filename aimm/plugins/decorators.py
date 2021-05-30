from typing import Optional, Callable, List, ClassVar

from aimm.plugins import common


_declarations_initial = {'data_access': {},
                         'instantiate': {},
                         'fit': {},
                         'predict': {},
                         'serialize': {},
                         'deserialize': {}}
_declarations = dict(_declarations_initial)


def data_access(name: str,
                state_cb_arg_name: Optional[str] = None) -> Callable:
    """Decorator used to indicate that the wrapped function is a data access
    function. The decorated function can take any number of positional and
    keyword arguments and should return the accessed data.

    Args:
        name: name of the data access type
        state_cb_arg_name: if set, indicates that the caller should pass a
            state callback function as a keyword argument and use the passed
            value as the argument name. The function is of type Callable[Any],
            where the only argument is JSON serializable data.

    Returns:
        Decorated function"""
    def decorator(function):
        _declare('data_access', name, common.DataAccessPlugin(
            function=function, state_cb_arg_name=state_cb_arg_name, name=name))
        return function

    return decorator


def instantiate(model_type: str,
                state_cb_arg_name: Optional[str] = None) -> Callable:
    """Decorator used to indicate that the wrapped function is a model instance
    creation function. The decorated function should take any number of
    positional and keyword arguments and should return the newly created model
    instance.

    Args:
        model_type: name of the model type
        state_cb_arg_name: if set, indicates that the caller should pass a
            state callback function as a keyword argument and use the passed
            value as the argument name. The function is of type Callable[Any].

    Returns:
        Decorated function"""
    def decorator(function):
        _declare('instantiate', model_type, common.InstantiatePlugin(
            function=function, state_cb_arg_name=state_cb_arg_name))
        return function

    return decorator


def fit(model_types: List[str],
        state_cb_arg_name: Optional[str] = None,
        instance_arg_name: Optional[str] = None) -> Callable:
    """Decorator used to indicate that the wrapped function is a fitting
    function. The decorated function should take at least one argument - model
    instance (passed as the first positional argument by default). It may also
    take any number of additional positional and keyword arguments and should
    return the updated model instance.

    Args:
        model_types: types of models supported by the decorated function
        state_cb_arg_name: if set, indicates that the caller should pass a
            state callback function as a keyword argument and use the passed
            value as the argument name. The function is of type Callable[Any]
        instance_arg_name: if set, indicates under which
            argument name to pass the concrete model instance. If not set, it
            is passed in the first positional argument

    Returns:
        Decorated function"""
    def decorator(function):
        for model_type in model_types:
            if model_type in _declarations['fit']:
                raise ValueError(f'duplicate fitting function under model '
                                 f'type {model_type}')
            _declare('fit', model_type, common.FitPlugin(
                function=function, state_cb_arg_name=state_cb_arg_name,
                instance_arg_name=instance_arg_name))
        return function

    return decorator


def predict(model_types: List[str],
            state_cb_arg_name: Optional[str] = None,
            instance_arg_name: Optional[str] = None) -> Callable:
    """Decorator used to indicate that the wrapped function is a prediction
    function. The decorated function should take at least one argument - model
    instance (passed as the first positional argument by default). It may also
    take any number of additional positional and keyword arguments and should
    return the updated model instance.

    Args:
        model_types: types of models supported by the decorated function
        state_cb_arg_name: if set, indicates that the caller should pass a
            state callback function as a keyword argument and use the passed
            value as the argument name. The function is of type Callable[Any]
        instance_arg_name: if set, indicates under which argument name to pass
            the concrete model instance. If not set, it is passed in the first
            positional argument

    Returns:
        Decorated function"""
    def decorator(function):
        for model_type in model_types:
            _declare('predict', model_type, common.PredictPlugin(
                function=function, state_cb_arg_name=state_cb_arg_name,
                instance_arg_name=instance_arg_name))
        return function

    return decorator


def serialize(model_types: List[str]) -> Callable:
    """Decorator used to indicate that the wrapped function is a serialize
    function. The decorated function should have the following signature:

    ``(instance: Any) -> ByteString``

    The return value is the byte representation of the model instance.

    Args:
        model_types: types of models supported by the decorated function
        instance_arg_name: if set, indicates under which argument name to pass
            the concrete model instance. If not set, it is passed in the first
            positional argument

    Returns:
        Decorated function"""
    def decorator(function):
        for model_type in model_types:
            _declare('serialize', model_type,
                     common.SerializePlugin(function=function))
        return function

    return decorator


def deserialize(model_types: List[str]) -> Callable:
    """Decorator used to indicate that the wrapped function is a
    deserialize function. The decorated function should have the following
    signature:

    ``(instance_bytes: ByteString) -> Any``

    The return value is the deserialized model instance.

    Args:
        model_types: types of models supported by the decorated function

    Returns:
        Decorated function"""
    def decorator(function):
        for model_type in model_types:
            _declare('deserialize', model_type,
                     common.DeserializePlugin(function=function))
        return function

    return decorator


def model(cls: ClassVar) -> ClassVar:
    """Model class decorator, used to mark that a class may be used as a model
    implementation. Model class unifies different plugin actions
    (:func:`instantiate` as ``__init__``, :func:`fit`, :func:`predict`,
    :func:`serialize`, :func:`deserialize` as their same-named class methods)
    under the same model type (module + class name). The class should implement
    the :class:`Model` interface.

    Args:
        cls (:class:`Model`): model class

    Returns:
        Decorated class
    """

    model_type = f'{cls.__module__}.{cls.__name__}'
    _declare('instantiate', model_type, common.InstantiatePlugin(cls))
    _declare('fit', model_type, common.FitPlugin(cls.fit))
    _declare('predict', model_type, common.PredictPlugin(cls.predict))
    _declare('serialize', model_type,
             common.SerializePlugin(cls.serialize))
    _declare('deserialize', model_type,
             common.DeserializePlugin(cls.deserialize))

    return cls


def get_instantiate(model_type: str) -> Callable:
    return _declarations['instantiate'][model_type]


def get_data_access(name: str) -> Callable:
    return _declarations['data_access'][name]


def get_fit(model_type: str) -> Callable:
    return _declarations['fit'][model_type]


def get_predict(model_type: str) -> Callable:
    return _declarations['predict'][model_type]


def get_serialize(model_type: str) -> Callable:
    return _declarations['serialize'][model_type]


def get_deserialize(model_type: str) -> Callable:
    return _declarations['deserialize'][model_type]


def unload_all():
    global _declarations
    _declarations = dict(_declarations_initial)


def _declare(declaration_type, key, plugin):
    global _declarations
    _declarations = dict(_declarations)
    declarations_typed = dict(_declarations[declaration_type])

    if key in declarations_typed:
        raise ValueError(f'plugin with type {key} already declared as '
                         f'{declaration_type}')
    declarations_typed[key] = plugin

    _declarations[declaration_type] = declarations_typed
