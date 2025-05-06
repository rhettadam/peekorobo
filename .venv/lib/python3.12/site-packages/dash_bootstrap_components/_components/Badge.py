# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Badge(Component):
    """A Badge component.
Badges can be used to add counts or labels to other components.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Badge.

- id (string; optional):
    The ID of the Badge.

- color (string; default 'secondary'):
    Badge color, options: primary, secondary, success, info, warning,
    danger, link or any valid CSS color of your choice (e.g. a hex
    code, a decimal code or a CSS color name).  Default: secondary.

- text_color (string; optional):
    Set the color of the text to one of the Bootstrap contextual
    colors.  Options: primary, secondary, success, info, warning,
    danger, light or dark.

- n_clicks (number; default 0):
    The number of times the Badge has been clicked.

- href (string; optional):
    A URL to link to when the Badge is clicked.

- external_link (boolean; optional):
    If True, clicking on the Badge will behave like a hyperlink. If
    False, the Badge will behave like a dcc.Link component, and can be
    used in conjunction with dcc.Location for navigation within a Dash
    app.

- pill (boolean; optional):
    Make badge \"pill\" shaped (rounded ends, like a pill). Default:
    False.

- class_name (string; optional):
    Additional CSS classes to apply to the Badge.

- tag (string; optional):
    HTML tag to use for the Badge. Default: span.

- target (string; optional):
    Target attribute to pass on to the link. Only applies to external
    links.

- title (string; optional):
    Sets the title attribute of the underlying HTML button.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Badge."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Badge'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        color: typing.Optional[str] = None,
        text_color: typing.Optional[str] = None,
        n_clicks: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        href: typing.Optional[str] = None,
        external_link: typing.Optional[bool] = None,
        pill: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        tag: typing.Optional[str] = None,
        target: typing.Optional[str] = None,
        title: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'color', 'text_color', 'n_clicks', 'href', 'external_link', 'pill', 'style', 'class_name', 'tag', 'target', 'title', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'color', 'text_color', 'n_clicks', 'href', 'external_link', 'pill', 'style', 'class_name', 'tag', 'target', 'title', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Badge, self).__init__(children=children, **args)
