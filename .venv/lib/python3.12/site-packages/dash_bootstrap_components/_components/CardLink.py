# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class CardLink(Component):
    """A CardLink component.
Use card link to add consistently styled links to your cards. Links can be
used like buttons, external links, or internal Dash style links.

Keyword arguments:

- id (string; optional):
    The ID of the CardLink.

- children (a list of or a singular dash component, string or number; optional):
    The children of this CardLink.

- href (string; optional):
    URL of the resource to link to.

- external_link (boolean; optional):
    If True, clicking on the CardLink will behave like a hyperlink. If
    False, the CardLink will behave like a dcc.Link component, and can
    be used in conjunction with dcc.Location for navigation within a
    Dash app.

- n_clicks (number; default 0):
    The number of times the CardLink has been clicked.

- class_name (string; optional):
    Additional CSS classes to apply to the CardLink.

- target (string; optional):
    Target attribute to pass on to the link. Only applies to external
    links.

- disabled (boolean; optional):
    If True, the link is disabled and can't be clicked on.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the CardLink."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'CardLink'

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
        target: typing.Optional[str] = None,
        disabled: typing.Optional[bool] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['id', 'children', 'href', 'external_link', 'n_clicks', 'style', 'class_name', 'target', 'disabled', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'children', 'href', 'external_link', 'n_clicks', 'style', 'class_name', 'target', 'disabled', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(CardLink, self).__init__(children=children, **args)
