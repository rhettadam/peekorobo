# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class NavLink(Component):
    """A NavLink component.
Add a link to a `Nav`. Can be used as a child of `NavItem` or of `Nav` directly.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the NavLink.

- id (string; optional):
    The ID of the NavLink.

- href (string; optional):
    The URL of the linked resource.

- n_clicks (number; default 0):
    The number of times the NavLink has been clicked.

- active (boolean | a value equal to: 'partial', 'exact'; default False):
    Apply 'active' style to this component. Set to \"exact\" to
    automatically toggle active status when the current pathname
    matches href, or to \"partial\" to automatically toggle on a
    partial match. Assumes that href is a relative url such as /link
    rather than an absolute such as https://example.com/link  For
    example - dbc.NavLink(..., href=\"/my-page\", active=\"exact\")
    will be active on   \"/my-page\" but not \"/my-page/other\" or
    \"/random\" - dbc.NavLink(..., href=\"/my-page\",
    active=\"partial\") will be active on   \"/my-page\" and
    \"/my-page/other\" but not \"/random\".

- disabled (boolean; default False):
    Disable the link.

- external_link (boolean; optional):
    If True, clicking on the NavLink will behave like a hyperlink. If
    False, the NavLink will behave like a dcc.Link component, and can
    be used in conjunction with dcc.Location for navigation within a
    Dash app.

- class_name (string; optional):
    Additional CSS classes to apply to the NavLink.

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
    to apply to the NavLink."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'NavLink'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        href: typing.Optional[str] = None,
        n_clicks: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        active: typing.Optional[typing.Union[bool, Literal["partial", "exact"]]] = None,
        disabled: typing.Optional[bool] = None,
        external_link: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        target: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'href', 'n_clicks', 'active', 'disabled', 'external_link', 'style', 'class_name', 'target', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'href', 'n_clicks', 'active', 'disabled', 'external_link', 'style', 'class_name', 'target', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(NavLink, self).__init__(children=children, **args)
