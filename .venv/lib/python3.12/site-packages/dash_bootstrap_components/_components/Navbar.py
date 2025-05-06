# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Navbar(Component):
    """A Navbar component.
The Navbar component can be used to make fully customisable navbars.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this component.

- id (string; optional):
    The ID of the component.

- dark (boolean; default True):
    Applies the `navbar-dark` class to the Navbar, causing text in the
    children of the Navbar to use light colors for contrast /
    visibility.

- fixed (string; optional):
    Fix the navbar's position at the top or bottom of the page,
    options: top, bottom.

- sticky (a value equal to: 'top'; optional):
    Position the navbar at the top of the viewport, but only after
    scrolling past it. A convenience prop for the sticky-top
    positioning class. Not supported in <= IE11 and other older
    browsers  With `sticky`, the navbar remains in the viewport when
    you scroll. By contrast, with `fixed`, the navbar will remain at
    the top or bottom of the page.  sticky='top'.

- color (string; default 'primary'):
    Sets the color of the Navbar. Main options are primary, light and
    dark, default primary.  You can also choose one of the other
    contextual classes provided by Bootstrap (secondary, success,
    warning, danger, info, white) or any valid CSS color of your
    choice (e.g. a hex code, a decimal code or a CSS color name).

- expand (boolean | string; default 'md'):
    Specify screen size at which to expand the menu bar, e.g. sm, md,
    lg etc.

- class_name (string; optional):
    Additional CSS classes to apply to the Navbar.

- role (string; optional):
    The ARIA role attribute.

- tag (string; optional):
    HTML tag to use for the Navbar, default 'nav'.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Navbar."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Navbar'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        dark: typing.Optional[bool] = None,
        fixed: typing.Optional[str] = None,
        sticky: typing.Optional[Literal["top"]] = None,
        color: typing.Optional[str] = None,
        expand: typing.Optional[typing.Union[bool, str]] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        role: typing.Optional[str] = None,
        tag: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'dark', 'fixed', 'sticky', 'color', 'expand', 'style', 'class_name', 'role', 'tag', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'dark', 'fixed', 'sticky', 'color', 'expand', 'style', 'class_name', 'role', 'tag', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Navbar, self).__init__(children=children, **args)
