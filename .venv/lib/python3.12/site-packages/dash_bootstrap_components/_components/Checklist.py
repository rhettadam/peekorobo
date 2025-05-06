# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Checklist(Component):
    """A Checklist component.
Checklist is a component that encapsulates several checkboxes.
The values and labels of the checklist is specified in the `options`
property and the checked items are specified with the `value` property.
Each checkbox is rendered as an input / label pair. `Checklist` must be
given an `id` to work properly.

Keyword arguments:

- options (list of dicts; optional):
    The options to display as items in the component. This can be an
    array or a dictionary as follows:  \n1. Array of options where the
    label and the value are the same thing - [string|number]  \n2. An
    array of options ``` {   \"label\": [string|number],   \"value\":
    [string|number],   \"disabled\": [bool] (Optional),
    \"input_id\": [string] (Optional),   \"label_id\": [string]
    (Optional) } ```  \n3. Simpler `options` representation in
    dictionary format. The order is not guaranteed. All values and
    labels will be treated as strings. ``` {\"value1\": \"label1\",
    \"value2\": \"label2\", ... } ``` which is equal to ``` [
    {\"label\": \"label1\", \"value\": \"value1\"},   {\"label\":
    \"label2\", \"value\": \"value2\"}, ] ```.

    `options` is a list of string | numbers | dict | list of dicts
    with keys:

    - label (a list of or a singular dash component, string or number; required):
        The checkbox's label.

    - value (string | number; required):
        The value of the checkbox. This value corresponds to the items
        specified in the `value` property.

    - disabled (boolean; optional):
        If True, this checkbox is disabled and can't be clicked on.

    - input_id (string; optional):
        id for this option's input, can be used to attach tooltips or
        apply CSS styles.

    - label_id (string; optional):
        id for this option's label, can be used to attach tooltips or
        apply CSS styles.

- value (list of string | numbers; optional):
    The currently selected values.

- id (string; optional):
    The ID of the Checklist.

- inline (boolean; optional):
    Arrange Checklist inline.

- switch (boolean; optional):
    Set to True to render toggle-like switches instead of checkboxes.

- class_name (string; optional):
    The class of the container (div).

- input_style (dict; optional):
    The style of the <input> checkbox element.

- input_checked_style (dict; optional):
    Additional inline style arguments to apply to <input> elements on
    checked items.

- input_class_name (string; optional):
    The class of the <input> checkbox element.

- input_checked_class_name (string; optional):
    Additional CSS classes to apply to the <input> element when the
    corresponding checkbox is checked.

- label_style (dict; optional):
    Inline style arguments to apply to the <label> element for each
    item.

- label_class_name (string; optional):
    CSS classes to apply to the <label> element for each item.

- label_checked_style (dict; optional):
    Additional inline style arguments to apply to <label> elements on
    checked items.

- label_checked_class_name (string; optional):
    Additional CSS classes to apply to the <label> element when the
    corresponding checkbox is checked.

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

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  The class of the
    container (div).

- inputClassName (string; optional):
    **DEPRECATED** Use `input_class_name` instead.  The class of the
    <input> checkbox element.

- inputStyle (dict; optional):
    **DEPRECATED** Use `input_style` instead.  The style of the
    <input> checkbox element.

- inputCheckedStyle (dict; optional):
    **DEPRECATED** Use `input_checked_style` instead.  Additional
    inline style arguments to apply to <input> elements on checked
    items.

- inputCheckedClassName (string; optional):
    **DEPRECATED** Use `input_checked_class_name` instead.  Additional
    CSS classes to apply to the <input> element when the corresponding
    checkbox is checked.

- labelStyle (dict; optional):
    **DEPRECATED** Use `label_style` instead.  Inline style arguments
    to apply to the <label> element for each item.

- labelClassName (string; optional):
    **DEPRECATED** Use `label_class_name` instead.  CSS classes to
    apply to the <label> element for each item.

- labelCheckedStyle (dict; optional):
    **DEPRECATED** Use `label_checked_style` instead.  Additional
    inline style arguments to apply to <label> elements on checked
    items.

- labelCheckedClassName (string; optional):
    **DEPRECATED** Use `label_checked_class_name` instead.  Additional
    CSS classes to apply to the <label> element when the corresponding
    checkbox is checked."""
    _children_props = ['options[].label']
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Checklist'
    Options = TypedDict(
        "Options",
            {
            "label": typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]],
            "value": typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]],
            "disabled": NotRequired[bool],
            "input_id": NotRequired[str],
            "label_id": NotRequired[str]
        }
    )

    _explicitize_dash_init = True

    def __init__(
        self,
        options: typing.Optional[typing.Union[typing.Sequence[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]], dict, typing.Sequence["Options"]]] = None,
        value: typing.Optional[typing.Sequence[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        inline: typing.Optional[bool] = None,
        switch: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        input_style: typing.Optional[dict] = None,
        input_checked_style: typing.Optional[dict] = None,
        input_class_name: typing.Optional[str] = None,
        input_checked_class_name: typing.Optional[str] = None,
        label_style: typing.Optional[dict] = None,
        label_class_name: typing.Optional[str] = None,
        label_checked_style: typing.Optional[dict] = None,
        label_checked_class_name: typing.Optional[str] = None,
        name: typing.Optional[str] = None,
        persistence: typing.Optional[typing.Union[bool, str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persisted_props: typing.Optional[typing.Sequence[Literal["value"]]] = None,
        persistence_type: typing.Optional[Literal["local", "session", "memory"]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        inputClassName: typing.Optional[str] = None,
        inputStyle: typing.Optional[dict] = None,
        inputCheckedStyle: typing.Optional[dict] = None,
        inputCheckedClassName: typing.Optional[str] = None,
        labelStyle: typing.Optional[dict] = None,
        labelClassName: typing.Optional[str] = None,
        labelCheckedStyle: typing.Optional[dict] = None,
        labelCheckedClassName: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['options', 'value', 'id', 'inline', 'switch', 'style', 'class_name', 'input_style', 'input_checked_style', 'input_class_name', 'input_checked_class_name', 'label_style', 'label_class_name', 'label_checked_style', 'label_checked_class_name', 'name', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className', 'inputClassName', 'inputStyle', 'inputCheckedStyle', 'inputCheckedClassName', 'labelStyle', 'labelClassName', 'labelCheckedStyle', 'labelCheckedClassName']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['options', 'value', 'id', 'inline', 'switch', 'style', 'class_name', 'input_style', 'input_checked_style', 'input_class_name', 'input_checked_class_name', 'label_style', 'label_class_name', 'label_checked_style', 'label_checked_class_name', 'name', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className', 'inputClassName', 'inputStyle', 'inputCheckedStyle', 'inputCheckedClassName', 'labelStyle', 'labelClassName', 'labelCheckedStyle', 'labelCheckedClassName']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        super(Checklist, self).__init__(**args)
