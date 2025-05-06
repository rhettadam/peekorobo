# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Alert(Component):
    """An Alert component.
Alert allows you to create contextual feedback messages on user actions.

Control the visibility using callbacks with the `is_open` prop, or set it to
auto-dismiss with the `duration` prop.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Alert.

- id (string; optional):
    The ID of the Alert.

- is_open (boolean; default True):
    Whether the Alert is open (i.e. visible to the user). Default:
    True.

- color (string; default 'success'):
    Alert color, options: primary, secondary, success, info, warning,
    danger, link or any valid CSS color of your choice (e.g. a hex
    code, a decimal code or a CSS color name)  Default: success.

- dismissable (boolean; optional):
    If True, add a close button that allows Alert to be dismissed.

- duration (number; optional):
    Duration in milliseconds after which the Alert dismisses itself.

- fade (boolean; optional):
    If True, a fade animation will be applied when `is_open` is
    toggled. If False the Alert will simply appear and disappear.

- class_name (string; optional):
    Additional CSS class to apply to the Alert.

- persistence (boolean | string | number; optional):
    Used to allow user interactions to be persisted when the page is
    refreshed. See https://dash.plotly.com/persistence for more
    details.

- persisted_props (list of a value equal to: 'is_open's; optional):
    Properties to persist. Since only `is_open` is supported, this
    prop can normally be ignored.

- persistence_type (a value equal to: 'local', 'session', 'memory'; optional):
    Where persisted user changes will be stored: - memory: only kept
    in memory, reset on page refresh. - local: window.localStorage,
    data is kept after the browser quit. - session:
    window.sessionStorage, data is cleared once the browser quit.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS class to
    apply to the Alert."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Alert'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        is_open: typing.Optional[bool] = None,
        color: typing.Optional[str] = None,
        dismissable: typing.Optional[bool] = None,
        duration: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        fade: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        persistence: typing.Optional[typing.Union[bool, str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persisted_props: typing.Optional[typing.Sequence[Literal["is_open"]]] = None,
        persistence_type: typing.Optional[Literal["local", "session", "memory"]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'is_open', 'color', 'dismissable', 'duration', 'fade', 'style', 'class_name', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'is_open', 'color', 'dismissable', 'duration', 'fade', 'style', 'class_name', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Alert, self).__init__(children=children, **args)
