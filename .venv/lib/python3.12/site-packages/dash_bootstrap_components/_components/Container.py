# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Container(Component):
    """A Container component.
Containers provide a means to center and horizontally pad your site’s contents.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Container.

- id (string; optional):
    The ID of the Container.

- fluid (boolean | string; optional):
    If True the container-fluid class will be applied, and the
    Container will expand to fill available space. A non-fluid
    container resizes responsively to a fixed width at the different
    breakpoints.  You can also set the fluid property to one of the
    Bootstrap breakpoints: \"sm\", \"md\", \"lg\", \"xl\" or \"xxl\",
    so that the container fluidly expands to fill the screen until the
    specified breakpoint, then resize responsively at higher
    breakpoints.

- class_name (string; optional):
    Additional CSS classes to apply to the Container.

- tag (string; optional):
    HTML tag to apply the container class to, default: div.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Container."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Container'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        fluid: typing.Optional[typing.Union[bool, str]] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        tag: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'fluid', 'style', 'class_name', 'tag', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'fluid', 'style', 'class_name', 'tag', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Container, self).__init__(children=children, **args)
