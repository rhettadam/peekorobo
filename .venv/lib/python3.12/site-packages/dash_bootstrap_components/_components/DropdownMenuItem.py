# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class DropdownMenuItem(Component):
    """A DropdownMenuItem component.
Use DropdownMenuItem to build up the content of a DropdownMenu.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this DropdownMenuItem.

- id (string; optional):
    The ID of the DropdownMenuItem.

- href (string; optional):
    A URL to link to, if the DropdownMenuItem is clicked.

- external_link (boolean; optional):
    If True, clicking on the DropdownMenuItem will behave like a
    hyperlink. If False, the DropdownMenuItem will behave like a
    dcc.Link component, and can be used in conjunction with
    dcc.Location for navigation within a Dash app.

- n_clicks (number; default 0):
    The number of times the DropdownMenuItem has been clicked.

- class_name (string; optional):
    Additional CSS classes to apply to the DropdownMenuItem.

- active (boolean; optional):
    Style this item as 'active'.

- disabled (boolean; optional):
    Style this item as 'disabled'.

- divider (boolean; optional):
    Set to True if this entry is a divider. Typically, it will have no
    children.

- header (boolean; optional):
    Set to True if this is a header, rather than a conventional menu
    item.

- toggle (boolean; default True):
    Whether to toggle the DropdownMenu on click. Default: True.

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
    to apply to the DropdownMenuItem."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'DropdownMenuItem'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        href: typing.Optional[str] = None,
        external_link: typing.Optional[bool] = None,
        n_clicks: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        active: typing.Optional[bool] = None,
        disabled: typing.Optional[bool] = None,
        divider: typing.Optional[bool] = None,
        header: typing.Optional[bool] = None,
        toggle: typing.Optional[bool] = None,
        target: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'href', 'external_link', 'n_clicks', 'style', 'class_name', 'active', 'disabled', 'divider', 'header', 'toggle', 'target', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'href', 'external_link', 'n_clicks', 'style', 'class_name', 'active', 'disabled', 'divider', 'header', 'toggle', 'target', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(DropdownMenuItem, self).__init__(children=children, **args)
