# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class FormFeedback(Component):
    """A FormFeedback component.
The FormFeedback component can be used to provide feedback on input values in a form.
Add the form feedback to your layout and set the `valid` or `invalid` props of the
associated input to toggle visibility.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this FormFeedback.

- id (string; optional):
    The ID of the FormFeedback.

- type (a value equal to: 'valid', 'invalid'; optional):
    Either 'valid' or 'invalid'.

- tooltip (boolean; optional):
    Use styled tooltips to display validation feedback.

- class_name (string; optional):
    Additional CSS classes to apply to the FormFeedback.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the FormFeedback."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'FormFeedback'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        type: typing.Optional[Literal["valid", "invalid"]] = None,
        tooltip: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'type', 'tooltip', 'style', 'class_name', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'type', 'tooltip', 'style', 'class_name', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(FormFeedback, self).__init__(children=children, **args)
