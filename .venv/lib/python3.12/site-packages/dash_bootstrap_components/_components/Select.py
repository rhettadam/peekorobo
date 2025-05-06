# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Select(Component):
    """A Select component.
Create a HTML select element with Bootstrap styles. Specify options as a list of
dictionaries with keys label, value and disabled.

Keyword arguments:

- options (list of dicts; optional):
    The options to display as items in the component. This can be an
    array or a dictionary as follows:  \n1. Array of options where the
    label and the value are the same thing - [string|number]  \n2. An
    array of options ``` {   \"label\": [string|number],   \"value\":
    [string|number],   \"disabled\": [bool] (Optional),   \"title\":
    [string] (Optional) } ```  \n3. Simpler `options` representation
    in dictionary format. The order is not guaranteed. All values and
    labels will be treated as strings. ``` {\"value1\": \"label1\",
    \"value2\": \"label2\", ... } ``` which is equal to ``` [
    {\"label\": \"label1\", \"value\": \"value1\"},   {\"label\":
    \"label2\", \"value\": \"value2\"}, ] ```.

    `options` is a list of string | numbers | dict | list of dicts
    with keys:

    - label (string | number; required):
        The options's label.

    - value (string; required):
        The value of the option. This value corresponds to the items
        specified in the `value` property.

    - disabled (boolean; optional):
        If True, this checkbox is disabled and can't be clicked on.

    - title (string; optional):
        The HTML 'title' attribute for the option. Allows for
        information on hover. For more information on this attribute,
        see
        https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/title.

- value (string | number; default ''):
    The value of the currently selected option.

- id (string; optional):
    The ID of the Select.

- placeholder (string; default ''):
    Placeholder text to display before a selection is made.

- disabled (boolean; optional):
    Set to True to disable the Select.

- class_name (string; optional):
    Additional CSS classes to apply to the Select.

- required (a value equal to: 'required', 'REQUIRED' | boolean; optional):
    This attribute specifies that the user must fill in a value before
    submitting a form. It cannot be used when the type attribute is
    hidden, image, or a button type (submit, reset, or button). The
    :optional and :required CSS pseudo-classes will be applied to the
    field as appropriate. required is an HTML boolean attribute - it
    is enabled by a boolean or 'required'. Alternative capitalizations
    `REQUIRED` are also acccepted.

- valid (boolean; optional):
    Apply valid style to the Input for feedback purposes. This will
    cause any FormFeedback in the enclosing div with valid=True to
    display.

- invalid (boolean; optional):
    Apply invalid style to the Input for feedback purposes. This will
    cause any FormFeedback in the enclosing div with valid=False to
    display.

- size (string; optional):
    Set the size of the Input. Options: 'sm' (small), 'md' (medium) or
    'lg' (large). Default is 'md'.

- html_size (string; optional):
    This represents the number of rows in the select that should be
    visible at one time. It will result in the Select being rendered
    as a scrolling list box rather than a dropdown.

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
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Select."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Select'
    Options = TypedDict(
        "Options",
            {
            "label": typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]],
            "value": str,
            "disabled": NotRequired[bool],
            "title": NotRequired[str]
        }
    )

    _explicitize_dash_init = True

    def __init__(
        self,
        options: typing.Optional[typing.Union[typing.Sequence[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]], dict, typing.Sequence["Options"]]] = None,
        value: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        placeholder: typing.Optional[str] = None,
        disabled: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        required: typing.Optional[typing.Union[Literal["required", "REQUIRED"], bool]] = None,
        valid: typing.Optional[bool] = None,
        invalid: typing.Optional[bool] = None,
        size: typing.Optional[str] = None,
        html_size: typing.Optional[str] = None,
        name: typing.Optional[str] = None,
        persistence: typing.Optional[typing.Union[bool, str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persisted_props: typing.Optional[typing.Sequence[Literal["value"]]] = None,
        persistence_type: typing.Optional[Literal["local", "session", "memory"]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['options', 'value', 'id', 'placeholder', 'disabled', 'style', 'class_name', 'required', 'valid', 'invalid', 'size', 'html_size', 'name', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['options', 'value', 'id', 'placeholder', 'disabled', 'style', 'class_name', 'required', 'valid', 'invalid', 'size', 'html_size', 'name', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        super(Select, self).__init__(**args)
