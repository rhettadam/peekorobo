# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Col(Component):
    """A Col component.
Col for creating Bootstrap columns to control the layout of your page.

Use the width argument to specify width, or use the breakpoint arguments
(xs, sm, md, lg, xl) to control the width of the columns on different screen
sizes to achieve a responsive layout.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this Col.

- id (string; optional):
    The ID of the Col.

- align (a value equal to: 'start', 'center', 'end', 'stretch', 'baseline'; optional):
    Set vertical alignment of this column's content in the parent row.
    Options are 'start', 'center', 'end', 'stretch', 'baseline'.

- class_name (string; optional):
    Additional CSS classes to apply to the Col.

- width (optional):
    Specify the width of the column. Behind the scenes this sets
    behaviour at the xs breakpoint, and will be overriden if xs is
    specified.  Valid arguments are boolean, an integer in the range
    1-12 inclusive, or a dictionary with keys 'offset', 'order',
    'size'. See the documentation for more details.

- xs (optional):
    Specify column behaviour on an extra small screen.  Valid
    arguments are boolean, an integer in the range 1-12 inclusive, or
    a dictionary with keys 'offset', 'order', 'size'. See the
    documentation for more details.

- sm (optional):
    Specify column behaviour on a small screen.  Valid arguments are
    boolean, an integer in the range 1-12 inclusive, or a dictionary
    with keys 'offset', 'order', 'size'. See the documentation for
    more details.

- md (optional):
    Specify column behaviour on a medium screen.  Valid arguments are
    boolean, an integer in the range 1-12 inclusive, or a dictionary
    with keys 'offset', 'order', 'size'. See the documentation for
    more details.

- lg (optional):
    Specify column behaviour on a large screen.  Valid arguments are
    boolean, an integer in the range 1-12 inclusive, or a dictionary
    with keys 'offset', 'order', 'size'. See the documentation for
    more details.

- xl (optional):
    Specify column behaviour on an extra large screen.  Valid
    arguments are boolean, an integer in the range 1-12 inclusive, or
    a dictionary with keys 'offset', 'order', 'size'. See the
    documentation for more details.

- xxl (optional):
    Specify column behaviour on an extra extra large screen.  Valid
    arguments are boolean, an integer in the range 1-12 inclusive, or
    a dictionary with keys 'offset', 'order', 'size'. See the
    documentation for more details.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Col."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Col'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        align: typing.Optional[Literal["start", "center", "end", "stretch", "baseline"]] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        width: typing.Optional[typing.Any] = None,
        xs: typing.Optional[typing.Any] = None,
        sm: typing.Optional[typing.Any] = None,
        md: typing.Optional[typing.Any] = None,
        lg: typing.Optional[typing.Any] = None,
        xl: typing.Optional[typing.Any] = None,
        xxl: typing.Optional[typing.Any] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'align', 'style', 'class_name', 'width', 'xs', 'sm', 'md', 'lg', 'xl', 'xxl', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'align', 'style', 'class_name', 'width', 'xs', 'sm', 'md', 'lg', 'xl', 'xxl', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Col, self).__init__(children=children, **args)
