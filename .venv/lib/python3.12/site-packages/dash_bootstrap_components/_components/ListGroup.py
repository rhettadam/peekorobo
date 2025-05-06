# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class ListGroup(Component):
    """A ListGroup component.
Bootstrap list groups are a flexible way to display a series of content. Use
in conjunction with `ListGroupItem`, `ListGroupItemHeading` and
`ListGroupItemText`.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the ListGroup.

- id (string; optional):
    The ID of the ListGroup.

- numbered (boolean; default False):
    Generate numbered list items.

- horizontal (boolean | string; optional):
    Set to True for a horizontal ListGroup, or supply one of the
    breakpoints as a string for a ListGroup that is horizontal at that
    breakpoint and up.  Note that horizontal ListGroups cannot be
    combined with flush ListGroups, so if flush is True then
    horizontal has no effect.

- flush (boolean; optional):
    When True the `list-group-flush` class is applied which removes
    some borders and rounded corners from the list group in order that
    they can be rendered edge-to-edge in the parent container (e.g. a
    Card).

- class_name (string; optional):
    Additional CSS classes to apply to the ListGroup.

- tag (string; default 'ul'):
    HTML tag to use for the list, default: ul.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the ListGroup."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'ListGroup'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        numbered: typing.Optional[bool] = None,
        horizontal: typing.Optional[typing.Union[bool, str]] = None,
        flush: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        tag: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'numbered', 'horizontal', 'flush', 'style', 'class_name', 'tag', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'numbered', 'horizontal', 'flush', 'style', 'class_name', 'tag', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(ListGroup, self).__init__(children=children, **args)
