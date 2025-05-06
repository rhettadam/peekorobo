# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class ListGroupItem(Component):
    """A ListGroupItem component.
Create a single item in a `ListGroup`.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this ListGroupItem.

- id (string; optional):
    The ID of the ListGroupItem.

- n_clicks (number; default 0):
    The number of times the ListGroupItem has been clicked.

- class_name (string; optional):
    Additional CSS classes to apply to the ListGroupItem.

- tag (string; optional):
    HTML tag to use for the ListGroupItem, default: li.

- active (boolean; optional):
    Set to True to apply the \"active\" style to this item.

- disabled (boolean; optional):
    If True, the item will be disabled.

- color (string; optional):
    Item color, options: primary, secondary, success, info, warning,
    danger, or any valid CSS color of your choice (e.g. a hex code, a
    decimal code or a CSS color name). Default: secondary.

- action (boolean; optional):
    Apply list-group-item-action class for hover animation etc.

- href (string; optional):
    Pass a URL (relative or absolute) to make the list group item a
    link.

- external_link (boolean; optional):
    If True, clicking on the ListGroupItem will behave like a
    hyperlink. If False, the ListGroupItem will behave like a dcc.Link
    component, and can be used in conjunction with dcc.Location for
    navigation within a Dash app.

- target (string; optional):
    Target attribute to pass on to the link. Only applies to external
    links.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the ListGroupItem."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'ListGroupItem'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        n_clicks: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        tag: typing.Optional[str] = None,
        active: typing.Optional[bool] = None,
        disabled: typing.Optional[bool] = None,
        color: typing.Optional[str] = None,
        action: typing.Optional[bool] = None,
        href: typing.Optional[str] = None,
        external_link: typing.Optional[bool] = None,
        target: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'n_clicks', 'style', 'class_name', 'tag', 'active', 'disabled', 'color', 'action', 'href', 'external_link', 'target', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'n_clicks', 'style', 'class_name', 'tag', 'active', 'disabled', 'color', 'action', 'href', 'external_link', 'target', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(ListGroupItem, self).__init__(children=children, **args)
