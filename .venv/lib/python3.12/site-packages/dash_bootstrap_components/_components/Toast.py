# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Toast(Component):
    """A Toast component.
Toasts can be used to push messages and notifactions to users. Control visibility of
the toast with the `is_open` prop, or use `duration` to set a timer for
auto-dismissal.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Toast.

- id (string; optional):
    The ID of the Toast.

- is_open (boolean; default True):
    Whether Toast is currently open.

- dismissable (boolean; default False):
    Set to True to add a dismiss button to the header which will close
    the toast on click.

- duration (number; optional):
    Duration in milliseconds after which the Alert dismisses itself.

- n_dismiss (number; default 0):
    An integer that represents the number of times that the dismiss
    button has been clicked on.

- header (a list of or a singular dash component, string or number; optional):
    Text to populate the header with.

- icon (string; optional):
    Add a contextually coloured icon to the header of the toast.
    Options are: \"primary\", \"secondary\", \"success\", \"warning\",
    \"danger\", \"info\", \"light\" or \"dark\".

- color (string; optional):
    Toast color, options: primary, secondary, success, info, warning,
    danger, light, dark. Default: secondary.

- class_name (string; optional):
    Additional CSS classes to apply to the Toast.

- header_style (dict; optional):
    Additional inline CSS styles to apply to the Toast header.

- header_class_name (string; optional):
    Additional CSS classes to apply to the Toast header.

- body_style (dict; optional):
    Additional CSS classes to apply to the Toast body.

- body_class_name (string; optional):
    Additional CSS classes to apply to the Toast body.

- tag (string; optional):
    HTML tag to use for the Toast, default: div.

- persistence (boolean | string | number; optional):
    Used to allow user interactions to be persisted when the page is
    refreshed. See https://dash.plotly.com/persistence for more
    details.

- persisted_props (list of a value equal to: 'is_open's; optional):
    Properties whose user interactions will persist after refreshing
    the component or the page. Since only `value` is allowed this prop
    can normally be ignored.

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
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Toast.

- headerClassName (string; optional):
    **DEPRECATED** Use `header_class_name` instead.  Additional CSS
    classes to apply to the Toast. The classes specified with this
    prop will be applied to the header of the toast.

- bodyClassName (string; optional):
    **DEPRECATED** Use `body_class_name` instead.  Additional CSS
    classes to apply to the Toast. The classes specified with this
    prop will be applied to the body of the toast."""
    _children_props = ['header']
    _base_nodes = ['header', 'children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Toast'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        is_open: typing.Optional[bool] = None,
        dismissable: typing.Optional[bool] = None,
        duration: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        n_dismiss: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        header: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        icon: typing.Optional[str] = None,
        color: typing.Optional[str] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        header_style: typing.Optional[dict] = None,
        header_class_name: typing.Optional[str] = None,
        body_style: typing.Optional[dict] = None,
        body_class_name: typing.Optional[str] = None,
        tag: typing.Optional[str] = None,
        persistence: typing.Optional[typing.Union[bool, str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persisted_props: typing.Optional[typing.Sequence[Literal["is_open"]]] = None,
        persistence_type: typing.Optional[Literal["local", "session", "memory"]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        headerClassName: typing.Optional[str] = None,
        bodyClassName: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'is_open', 'dismissable', 'duration', 'n_dismiss', 'header', 'icon', 'color', 'style', 'class_name', 'header_style', 'header_class_name', 'body_style', 'body_class_name', 'tag', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className', 'headerClassName', 'bodyClassName']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'is_open', 'dismissable', 'duration', 'n_dismiss', 'header', 'icon', 'color', 'style', 'class_name', 'header_style', 'header_class_name', 'body_style', 'body_class_name', 'tag', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className', 'headerClassName', 'bodyClassName']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Toast, self).__init__(children=children, **args)
