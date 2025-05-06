# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Progress(Component):
    """A Progress component.
Component for displaying progress bars, with support for stacked bars, animated
backgrounds, and text labels.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this Progress. Use this to nest progress bars.

- id (string; optional):
    The ID of the Progress.

- value (string | number; optional):
    Specify progress, value from min to max inclusive.

- label (string; optional):
    Adds a label to the progress bar.

- min (number; optional):
    Lower limit for value, default: 0.

- max (number; optional):
    Upper limit for value, default: 100.

- color (string; optional):
    Set color of the progress bar, options: primary, secondary,
    success, warning, danger, info or any valid CSS color of your
    choice (e.g. a hex code, a decimal code or a CSS color name).

- bar (boolean; optional):
    Set to True when nesting Progress inside another Progress
    component to create a multi-progress bar.

- hide_label (boolean; default False):
    Set to True to hide the label.

- animated (boolean; optional):
    Animate the bar, must have striped set to True to work.

- striped (boolean; optional):
    Use striped progress bar.

- class_name (string; optional):
    Additional CSS classes to apply to the Progress.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Progress."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Progress'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        value: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        label: typing.Optional[str] = None,
        min: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        max: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        color: typing.Optional[str] = None,
        bar: typing.Optional[bool] = None,
        hide_label: typing.Optional[bool] = None,
        animated: typing.Optional[bool] = None,
        striped: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'value', 'label', 'min', 'max', 'color', 'bar', 'hide_label', 'animated', 'striped', 'style', 'class_name', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'value', 'label', 'min', 'max', 'color', 'bar', 'hide_label', 'animated', 'striped', 'style', 'class_name', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Progress, self).__init__(children=children, **args)
