# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Nav(Component):
    """A Nav component.
Nav can be used to group together a collection of navigation links.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Nav.

- id (string; optional):
    The ID of the Nav.

- pills (boolean; optional):
    Apply pill styling to nav items. Active items will be indicated by
    a pill.

- vertical (boolean | string; optional):
    Stack NavItems vertically. Set to True for a vertical Nav on all
    screen sizes, or pass one of the Bootstrap breakpoints ('xs',
    'sm', 'md', 'lg', 'xl') for a Nav which is vertical at that
    breakpoint and above, and horizontal on smaller screens.

- horizontal (a value equal to: 'start', 'center', 'end', 'between', 'around'; optional):
    Specify the horizontal alignment of the NavItems. Options are
    'start', 'center', or 'end'.

- fill (boolean; optional):
    Expand the nav items to fill available horizontal space.

- justified (boolean; optional):
    Expand the nav items to fill available horizontal space, making
    sure every nav item has the same width.

- card (boolean; optional):
    Set to True when using Nav with pills styling inside a CardHeader.

- navbar (boolean; optional):
    Set to True if using Nav in Navbar component. This applies the
    `navbar-nav` class to the Nav which uses more lightweight styles
    to match the parent Navbar better.

- navbar_scroll (boolean; optional):
    Enable vertical scrolling within the toggleable contents of a
    collapsed Navbar.

- class_name (string; optional):
    Additional CSS classes to apply to the Nav.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Nav."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Nav'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        pills: typing.Optional[bool] = None,
        vertical: typing.Optional[typing.Union[bool, str]] = None,
        horizontal: typing.Optional[Literal["start", "center", "end", "between", "around"]] = None,
        fill: typing.Optional[bool] = None,
        justified: typing.Optional[bool] = None,
        card: typing.Optional[bool] = None,
        navbar: typing.Optional[bool] = None,
        navbar_scroll: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'pills', 'vertical', 'horizontal', 'fill', 'justified', 'card', 'navbar', 'navbar_scroll', 'style', 'class_name', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'pills', 'vertical', 'horizontal', 'fill', 'justified', 'card', 'navbar', 'navbar_scroll', 'style', 'class_name', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Nav, self).__init__(children=children, **args)
