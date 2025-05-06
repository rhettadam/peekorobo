# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Label(Component):
    """A Label component.
A component for adding labels to inputs in forms with added sizing controls.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this Label.

- id (string; optional):
    The ID of the Label.

- size (string; optional):
    Set size of label. Options 'sm', 'md' (default) or 'lg'.

- html_for (string; optional):
    Set the `for` attribute of the label to bind it to a particular
    element.

- class_name (string; optional):
    Additional CSS classes to apply to the Label.

- hidden (boolean; optional):
    Hide label from UI, but allow it to be discovered by
    screen-readers.

- check (boolean; optional):
    Set to True when using to label a Checkbox or RadioButton.

- width (optional):
    Specify width of label for use in grid layouts. Accepts the same
    values as the Col component.

- xs (optional):
    Specify label width on extra small screen  Valid arguments are
    boolean, an integer in the range 1-12 inclusive, or a dictionary
    with keys 'offset', 'order', 'size'. See the documentation for
    more details.

- sm (optional):
    Specify label width on a small screen  Valid arguments are
    boolean, an integer in the range 1-12 inclusive, or a dictionary
    with keys 'offset', 'order', 'size'. See the documentation for
    more details.

- md (optional):
    Specify label width on a medium screen  Valid arguments are
    boolean, an integer in the range 1-12 inclusive, or a dictionary
    with keys 'offset', 'order', 'size'. See the documentation for
    more details.

- lg (optional):
    Specify label width on a large screen  Valid arguments are
    boolean, an integer in the range 1-12 inclusive, or a dictionary
    with keys 'offset', 'order', 'size'. See the documentation for
    more details.

- xl (optional):
    Specify label width on an extra large screen  Valid arguments are
    boolean, an integer in the range 1-12 inclusive, or a dictionary
    with keys 'offset', 'order', 'size'. See the documentation for
    more details.

- xxl (optional):
    Specify label width on an extra extra large screen  Valid
    arguments are boolean, an integer in the range 1-12 inclusive, or
    a dictionary with keys 'offset', 'order', 'size'. See the
    documentation for more details.

- align (a value equal to: 'start', 'center', 'end'; default 'center'):
    Set vertical alignment of the label, options: 'start', 'center',
    'end', default: 'center'.

- color (string; optional):
    Text color, options: primary, secondary, success, warning, danger,
    info, muted, light, dark, body, white, black-50, white-50 or any
    valid CSS color of your choice (e.g. a hex code, a decimal code or
    a CSS color name).

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Label."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Label'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        size: typing.Optional[str] = None,
        html_for: typing.Optional[str] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        hidden: typing.Optional[bool] = None,
        check: typing.Optional[bool] = None,
        width: typing.Optional[typing.Any] = None,
        xs: typing.Optional[typing.Any] = None,
        sm: typing.Optional[typing.Any] = None,
        md: typing.Optional[typing.Any] = None,
        lg: typing.Optional[typing.Any] = None,
        xl: typing.Optional[typing.Any] = None,
        xxl: typing.Optional[typing.Any] = None,
        align: typing.Optional[Literal["start", "center", "end"]] = None,
        color: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'size', 'html_for', 'style', 'class_name', 'hidden', 'check', 'width', 'xs', 'sm', 'md', 'lg', 'xl', 'xxl', 'align', 'color', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'size', 'html_for', 'style', 'class_name', 'hidden', 'check', 'width', 'xs', 'sm', 'md', 'lg', 'xl', 'xxl', 'align', 'color', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Label, self).__init__(children=children, **args)
