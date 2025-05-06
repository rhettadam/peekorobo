# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class RadioButton(Component):
    """A RadioButton component.
Render a single radio button.

Keyword arguments:

- id (string; optional):
    The ID of the RadioButton.

- value (boolean; default False):
    The value of the input.

- disabled (boolean; default False):
    Disable the RadioButton.

- class_name (string; optional):
    CSS classes to apply to the container (div).

- input_style (dict; optional):
    Inline CSS styles to apply to the <input> element.

- input_class_name (string; optional):
    Additional CSS classes to apply to the <input> element.

- label (a list of or a singular dash component, string or number; optional):
    The label of the <input> element.

- label_id (string; optional):
    The id of the label.

- label_style (dict; optional):
    Additional inline CSS styles to add to the label.

- label_class_name (string; optional):
    Additional CSS classes to apply to the label.

- name (string; optional):
    The name of the control, which is submitted with the form data.

- persistence (boolean | string | number; optional):
    Used to allow user interactions to be persisted when the page is
    refreshed. See https://dash.plotly.com/persistence for more
    details.

- persisted_props (list of a value equal to: 'value's; optional):
    Properties whose user interactions will persist after refreshing
    the component or the page. Since only `value` is allowed this prop
    can normally be ignored.

- persistence_type (a value equal to: 'local', 'session', 'memory'; optional):
    Where persisted user changes will be stored: - memory: only kept
    in memory, reset on page refresh. - local: window.localStorage,
    data is kept after the browser quit. - session:
    window.sessionStorage, data is cleared once the browser quit.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the container div.

- inputStyle (dict; optional):
    **DEPRECATED** Use `input_style` instead.  Additional inline CSS
    styles to apply to the <input> element.

- inputClassName (string; optional):
    **DEPRECATED** Use `input_class_name` instead.  Additional CSS
    classes to apply to the <input> element.

- labelStyle (dict; optional):
    **DEPRECATED** Use `label_style` instead.  Additional inline CSS
    styles to add to the label.

- labelClassName (string; optional):
    **DEPRECATED** Use `label_class_name` instead.  Additional CSS
    classes to apply to the label."""
    _children_props = ['label']
    _base_nodes = ['label', 'children']
    _namespace = 'dash_bootstrap_components'
    _type = 'RadioButton'

    _explicitize_dash_init = True

    def __init__(
        self,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        value: typing.Optional[bool] = None,
        disabled: typing.Optional[bool] = None,
        class_name: typing.Optional[str] = None,
        style: typing.Optional[typing.Any] = None,
        input_style: typing.Optional[dict] = None,
        input_class_name: typing.Optional[str] = None,
        label: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        label_id: typing.Optional[str] = None,
        label_style: typing.Optional[dict] = None,
        label_class_name: typing.Optional[str] = None,
        name: typing.Optional[str] = None,
        persistence: typing.Optional[typing.Union[bool, str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persisted_props: typing.Optional[typing.Sequence[Literal["value"]]] = None,
        persistence_type: typing.Optional[Literal["local", "session", "memory"]] = None,
        className: typing.Optional[str] = None,
        inputStyle: typing.Optional[dict] = None,
        inputClassName: typing.Optional[str] = None,
        labelStyle: typing.Optional[dict] = None,
        labelClassName: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['id', 'value', 'disabled', 'class_name', 'style', 'input_style', 'input_class_name', 'label', 'label_id', 'label_style', 'label_class_name', 'name', 'persistence', 'persisted_props', 'persistence_type', 'className', 'inputStyle', 'inputClassName', 'labelStyle', 'labelClassName']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'value', 'disabled', 'class_name', 'style', 'input_style', 'input_class_name', 'label', 'label_id', 'label_style', 'label_class_name', 'name', 'persistence', 'persisted_props', 'persistence_type', 'className', 'inputStyle', 'inputClassName', 'labelStyle', 'labelClassName']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        super(RadioButton, self).__init__(**args)
