# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class CardImg(Component):
    """A CardImg component.
Use CardImg to add images to your cards.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the CardImg.

- id (string; optional):
    The ID of the CardImg.

- src (string; optional):
    The URI of the embeddable content.

- class_name (string; optional):
    Additional CSS classes to apply to the CardImg.

- tag (string; optional):
    HTML tag to use for the CardImg, default: img.

- top (boolean; optional):
    If True the card-img-top class will be applied which rounds the
    top corners of the image to match the corners of the card.

- bottom (boolean; optional):
    If True the card-img-bottom class will be applied which rounds the
    bottom corners of the image to match the corners of the card.

- alt (string; optional):
    Alternative text in case an image can't be displayed.

- title (string; optional):
    Text to be displayed as a tooltip when hovering.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the CardImg."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'CardImg'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        src: typing.Optional[str] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        tag: typing.Optional[str] = None,
        top: typing.Optional[bool] = None,
        bottom: typing.Optional[bool] = None,
        alt: typing.Optional[str] = None,
        title: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'src', 'style', 'class_name', 'tag', 'top', 'bottom', 'alt', 'title', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'src', 'style', 'class_name', 'tag', 'top', 'bottom', 'alt', 'title', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(CardImg, self).__init__(children=children, **args)
