# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class NavbarSimple(Component):
    """A NavbarSimple component.
A self-contained navbar ready for use. If you need more customisability try
`Navbar` instead.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this NavbarSimple.

- id (string; optional):
    The ID of the NavbarSimple.

- color (string; default 'primary'):
    Sets the color of the NavbarSimple. Main options are primary,
    light and dark, default light.  You can also choose one of the
    other contextual classes provided by Bootstrap (secondary,
    success, warning, danger, info, white) or any valid CSS color of
    your choice (e.g. a hex code, a decimal code or a CSS color name).

- dark (boolean; default True):
    Applies the `navbar-dark` class to the NavbarSimple, causing text
    in the children of the Navbar to use light colors for contrast /
    visibility.

- fluid (boolean; default False):
    The contents of the Navbar are wrapped in a container, use
    fluid=True to make this container fluid, so that in particular,
    the contents of the navbar fill the available horizontal space.

- links_left (boolean; default False):
    Align the navlinks in the navbar to the left. Default: False.

- brand (a list of or a singular dash component, string or number; optional):
    Brand (text or dash components) that will be rendered on the top
    left of the Navbar.

- brand_href (string; optional):
    A URL to link to when the brand is clicked.

- brand_external_link (boolean; optional):
    If True, clicking on the brand link will behave like a hyperlink.
    If False, the brand link will behave like a dcc.Link component,
    and can be used in conjunction with dcc.Location for navigation
    within a Dash app.

- fixed (string; optional):
    Fix the navbar's position at the top or bottom of the page,
    options: top, bottom.

- sticky (string; optional):
    Stick the navbar to the top or the bottom of the viewport,
    options: top, bottom  With `sticky`, the navbar remains in the
    viewport when you scroll. By contrast, with `fixed`, the navbar
    will remain at the top or bottom of the page.

- expand (boolean | string; default 'md'):
    Specify breakpoint at which to expand the menu bar. Options are:
    'xs', 'sm', 'md', 'lg', or 'xl'. Below this breakpoint the navbar
    will collapse and navitems will be placed in a togglable collapse
    element.

- class_name (string; optional):
    Additional CSS classes to apply to the NavbarSimple.

- brand_style (dict; optional):
    CSS style options for brand.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the NavbarSimple."""
    _children_props = ['brand']
    _base_nodes = ['brand', 'children']
    _namespace = 'dash_bootstrap_components'
    _type = 'NavbarSimple'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        color: typing.Optional[str] = None,
        dark: typing.Optional[bool] = None,
        fluid: typing.Optional[bool] = None,
        links_left: typing.Optional[bool] = None,
        brand: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        brand_href: typing.Optional[str] = None,
        brand_external_link: typing.Optional[bool] = None,
        fixed: typing.Optional[str] = None,
        sticky: typing.Optional[str] = None,
        expand: typing.Optional[typing.Union[bool, str]] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        brand_style: typing.Optional[dict] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'color', 'dark', 'fluid', 'links_left', 'brand', 'brand_href', 'brand_external_link', 'fixed', 'sticky', 'expand', 'style', 'class_name', 'brand_style', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'color', 'dark', 'fluid', 'links_left', 'brand', 'brand_href', 'brand_external_link', 'fixed', 'sticky', 'expand', 'style', 'class_name', 'brand_style', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(NavbarSimple, self).__init__(children=children, **args)
