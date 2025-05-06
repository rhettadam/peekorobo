# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Card(Component):
    """A Card component.
Component for creating Bootstrap cards. Use in conjunction with CardBody, CardImg,
CardLink, CardHeader and CardFooter. Can also be used in conjunction with
CardColumns, CardDeck, CardGroup for different layout options.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this Card.

- id (string; optional):
    The ID of the Card.

- color (string; optional):
    Card color, options: primary, secondary, success, info, warning,
    danger, light, dark or any valid CSS color of your choice (e.g. a
    hex code, a decimal code or a CSS color name).  Default is light.

- body (boolean; optional):
    Apply the `card-body` class to the card, so that there is no need
    to also include a CardBody component in the children of this Card.
    Default: False.

- outline (boolean; optional):
    Apply color styling to just the border of the Card.

- inverse (boolean; optional):
    Invert text colours for use with a darker background.

- class_name (string; optional):
    Additional CSS classes to apply to the Card.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Card."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Card'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        color: typing.Optional[str] = None,
        body: typing.Optional[bool] = None,
        outline: typing.Optional[bool] = None,
        inverse: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'color', 'body', 'outline', 'inverse', 'style', 'class_name', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'color', 'body', 'outline', 'inverse', 'style', 'class_name', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Card, self).__init__(children=children, **args)
