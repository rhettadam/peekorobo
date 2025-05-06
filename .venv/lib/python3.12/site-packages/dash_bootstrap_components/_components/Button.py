# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Button(Component):
    """A Button component.
A component for creating Bootstrap buttons with different style options. The
Button component can act as a HTML button, link (<a>) or can be used like a
dash_core_components style `Link` for navigating between pages of a Dash app.

Use the `n_clicks` prop to trigger callbacks when the button has been
clicked.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this Button.

- id (string; optional):
    The ID of the Button.

- n_clicks (number; default 0):
    The number of times the Button has been clicked.

- color (string; optional):
    Button color, options: primary, secondary, success, info, warning,
    danger, link. Default: primary.

- href (string; optional):
    A URL to link to. If this property is set, the Button will behave
    like a dcc.Link for relative links, and like an html <a> tag for
    external links. This can be overridden with the `external_link`
    property.

- external_link (boolean; optional):
    If True, clicking on the Button will behave like a hyperlink. If
    False, the Button will behave like a dcc.Link component, and can
    be used in conjunction with dcc.Location for navigation within a
    Dash app.

- class_name (string; optional):
    Additional CSS classes to apply to the Button.

- active (boolean; optional):
    If True, the 'active' class is applied to the Button. Default:
    False.

- disabled (boolean; optional):
    If True, the Button will be disabled. Default: False.

- size (string; optional):
    The size of the Button. Options: 'sm', 'md', 'lg'.

- title (string; optional):
    The title of the Button.

- outline (boolean; optional):
    If True, the outline style is applied to the Button. Default:
    False.

- target (string; optional):
    The target attribute to pass on to the link. Only applies to
    external links.

- type (a value equal to: 'button', 'reset', 'submit'; optional):
    The default behavior of the button. Possible values are:
    \"button\", \"reset\", \"submit\". If left unspecified the default
    depends on usage: for buttons associated with a form (e.g. a
    dbc.Button inside a dbc.Form) the default is \"submit\". Otherwise
    the default is \"button\".

- download (string; optional):
    If the Button is a link, this attribute specifies that the target
    will be downloaded.

- name (string; optional):
    The name of the button, submitted as a pair with the button’s
    value as part of the form data.

- value (string; optional):
    Defines the value associated with the button’s name when it’s
    submitted with the form data. This value is passed to the server
    in params when the form is submitted.

- rel (string; optional):
    Set the rel attribute when Button is being used as a Link.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Button."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Button'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        n_clicks: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        color: typing.Optional[str] = None,
        href: typing.Optional[str] = None,
        external_link: typing.Optional[bool] = None,
        class_name: typing.Optional[str] = None,
        style: typing.Optional[typing.Any] = None,
        active: typing.Optional[bool] = None,
        disabled: typing.Optional[bool] = None,
        size: typing.Optional[str] = None,
        title: typing.Optional[str] = None,
        outline: typing.Optional[bool] = None,
        target: typing.Optional[str] = None,
        type: typing.Optional[Literal["button", "reset", "submit"]] = None,
        download: typing.Optional[str] = None,
        name: typing.Optional[str] = None,
        value: typing.Optional[str] = None,
        rel: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'n_clicks', 'color', 'href', 'external_link', 'class_name', 'style', 'active', 'disabled', 'size', 'title', 'outline', 'target', 'type', 'download', 'name', 'value', 'rel', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'n_clicks', 'color', 'href', 'external_link', 'class_name', 'style', 'active', 'disabled', 'size', 'title', 'outline', 'target', 'type', 'download', 'name', 'value', 'rel', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Button, self).__init__(children=children, **args)
