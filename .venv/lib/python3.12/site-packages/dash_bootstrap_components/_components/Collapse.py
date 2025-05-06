# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Collapse(Component):
    """A Collapse component.
Hide or show content with a vertical collapsing animation. Visibility of the
children is controlled by the `is_open` prop which can be targetted by
callbacks.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Collapse.

- id (string; optional):
    The ID of the Collapse.

- is_open (boolean; optional):
    Whether collapse is currently open.

- dimension (a value equal to: 'height', 'width'; default 'height'):
    The dimension used when collapsing e.g. height will collapse
    vertically, whilst width will collapse horizontally.

- navbar (boolean; optional):
    Set to True when using a collapse inside a navbar.

- class_name (string; optional):
    Additional CSS classes to apply to the Collapse.

- tag (string; optional):
    The HTML tag used for the collapse component.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Collapse."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Collapse'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        is_open: typing.Optional[bool] = None,
        dimension: typing.Optional[Literal["height", "width"]] = None,
        navbar: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        tag: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'is_open', 'dimension', 'navbar', 'style', 'class_name', 'tag', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'is_open', 'dimension', 'navbar', 'style', 'class_name', 'tag', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Collapse, self).__init__(children=children, **args)
