# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class NavbarBrand(Component):
    """A NavbarBrand component.
Call out attention to a brand name or site title within a Navbar.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this NavbarBrand.

- id (string; optional):
    The ID of the NavbarBrand.

- external_link (boolean; optional):
    If True, clicking on the NavbarBrand will behave like a hyperlink.
    If False, the NavbarBrand will behave like a dcc.Link component,
    and can be used in conjunction with dcc.Location for navigation
    within a Dash app.

- href (string; optional):
    URL of the linked resource.

- class_name (string; optional):
    Additional CSS classes to apply to the NavbarBrand.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the NavbarBrand."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'NavbarBrand'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        external_link: typing.Optional[bool] = None,
        href: typing.Optional[str] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'external_link', 'href', 'style', 'class_name', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'external_link', 'href', 'style', 'class_name', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(NavbarBrand, self).__init__(children=children, **args)
