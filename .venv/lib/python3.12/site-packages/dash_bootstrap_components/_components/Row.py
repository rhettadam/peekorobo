# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Row(Component):
    """A Row component.
Row is one of the core layout components in Bootstrap. Build up your layout as a
series of rows of columns. Row has arguments for controlling the vertical and
horizontal alignment of its children, as well as the spacing between columns.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Row.

- id (string; optional):
    The ID of the Row.

- class_name (string; optional):
    Additional CSS classes to apply to the Row.

- align (a value equal to: 'start', 'center', 'end', 'stretch', 'baseline'; optional):
    Set vertical alignment of columns in this row. Options are
    'start', 'center', 'end', 'stretch' and 'baseline'.

- justify (a value equal to: 'start', 'center', 'end', 'around', 'between', 'evenly'; optional):
    Set horizontal spacing and alignment of columns in this row.
    Options are 'start', 'center', 'end', 'around' and 'between'.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Row."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Row'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        align: typing.Optional[Literal["start", "center", "end", "stretch", "baseline"]] = None,
        justify: typing.Optional[Literal["start", "center", "end", "around", "between", "evenly"]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'style', 'class_name', 'align', 'justify', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'style', 'class_name', 'align', 'justify', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Row, self).__init__(children=children, **args)
