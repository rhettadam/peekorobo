# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Table(Component):
    """A Table component.
A component for applying Bootstrap styles to HTML tables. Use this as a drop-in
replacement for `html.Table`, or generate a table from a Pandas DataFrame using
`dbc.Table.from_dataframe`.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this Table.

- id (string; optional):
    The ID of the Table.

- class_name (string; optional):
    Additional CSS classes to apply to the Table.

- size (string; optional):
    Specify table size, options: 'sm', 'md', 'lg'.

- bordered (boolean; optional):
    Apply the `table-bordered` class which adds borders on all sides
    of the table and cells.

- borderless (boolean; optional):
    Apply the `table-borderless` class which removes all borders from
    the table and cells.

- striped (boolean; optional):
    Apply the `table-striped` class which applies 'zebra striping' to
    rows in the table body.

- color (string; optional):
    Table color, options: primary, secondary, success, info, warning,
    danger, dark, light. Default: secondary.

- hover (boolean; optional):
    Apply the `table-hover` class which enables a hover state on table
    rows within the table body.

- responsive (boolean | string; optional):
    Set to True or one of the breakpoints 'sm', 'md', 'lg', 'xl' to
    make table scroll horizontally at lower breakpoints.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Table."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Table'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        size: typing.Optional[str] = None,
        bordered: typing.Optional[bool] = None,
        borderless: typing.Optional[bool] = None,
        striped: typing.Optional[bool] = None,
        color: typing.Optional[str] = None,
        hover: typing.Optional[bool] = None,
        responsive: typing.Optional[typing.Union[bool, str]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'style', 'class_name', 'size', 'bordered', 'borderless', 'striped', 'color', 'hover', 'responsive', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'style', 'class_name', 'size', 'bordered', 'borderless', 'striped', 'color', 'hover', 'responsive', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Table, self).__init__(children=children, **args)
