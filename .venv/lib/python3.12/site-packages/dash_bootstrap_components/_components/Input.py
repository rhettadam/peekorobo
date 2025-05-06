# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Input(Component):
    """An Input component.
A basic HTML input control for entering text, numbers, or passwords, with
Bootstrap styles automatically applied. This component is much like its
counterpart in dash_core_components, but with a few additions such as the
`valid` and `invalid` props for providing user feedback.

Note that checkbox and radio types are supported through
the Checklist and RadioItems component. Dates, times, and file uploads
are supported through separate components in other libraries.

Keyword arguments:

- id (string; optional):
    The ID of the Input.

- value (string | number; optional):
    The value of the Input.

- n_submit (number; default 0):
    Number of times the `Enter` key was pressed while the input had
    focus.

- n_blur (number; default 0):
    Number of times the input lost focus.

- size (string; optional):
    Set the size of the Input. Options: 'sm' (small), 'md' (medium) or
    'lg' (large). Default is 'md'.

- valid (boolean; optional):
    Apply valid style to the Input for feedback purposes. This will
    cause any FormFeedback in the enclosing div with valid=True to
    display.

- invalid (boolean; optional):
    Apply invalid style to the Input for feedback purposes. This will
    cause any FormFeedback in the enclosing div with valid=False to
    display.

- plaintext (boolean; optional):
    Set to True for an input styled as plain text with the default
    form field styling removed and the correct margins and padding
    preserved. Typically you will want to use this in conjunction with
    readonly=True.

- class_name (string; optional):
    Additional CSS classes to apply to the Input.

- type (a value equal to: 'text', 'number', 'password', 'email', 'range', 'search', 'tel', 'url', 'hidden', 'time'; optional):
    The type of control to render.

- step (string | number; default 'any'):
    Works with the min and max attributes to limit the increments at
    which a numeric or date-time value can be set. It can be the
    string any or a positive floating point number. If this attribute
    is not set to any, the control accepts only values at multiples of
    the step value greater than the minimum.

- disabled (boolean; optional):
    Set to True to disable the Input.

- placeholder (string | number; optional):
    A hint to the user of what can be entered in the control. The
    placeholder text must not contain carriage returns or line-feeds.
    Note: Do not use the placeholder attribute instead of a <label>
    element, their purposes are different. The <label> attribute
    describes the role of the form element (i.e. it indicates what
    kind of information is expected), and the placeholder attribute is
    a hint about the format that the content should take. There are
    cases in which the placeholder attribute is never displayed to the
    user, so the form must be understandable without it.

- debounce (boolean | number; default False):
    If True, changes to the Input will be sent back to the Dash server
    only when the enter key is pressed or when the component loses
    focus. If False, the Input will trigger a callback on every
    change. If debounce is a number, the value will be sent to the
    server only after the user has stopped typing for that number of
    milliseconds.

- html_size (string; optional):
    The initial size of the control. This value is in pixels unless
    the value of the type attribute is text or password, in which case
    it is an integer number of characters. This attribute applies only
    when the type attribute is set to text, search, tel, url, email,
    or password, otherwise it is ignored. In addition, the size must
    be greater than zero. If you do not specify a size, a default
    value of 20 is used.

- autocomplete (string; optional):
    This attribute indicates whether the value of the control can be
    automatically completed by the browser.

- autofocus (a value equal to: 'autoFocus', 'autofocus', 'AUTOFOCUS' | boolean; optional):
    The element should be automatically focused after the page loaded.
    autoFocus is an HTML boolean attribute - it is enabled by a
    boolean or 'autoFocus'. Alternative capitalizations `autofocus` &
    `AUTOFOCUS` are also acccepted.

- inputmode (a value equal to: 'verbatim', 'latin', 'latin-name', 'latin-prose', 'full-width-latin', 'kana', 'katakana', 'numeric', 'tel', 'email', 'url'; optional):
    Provides a hint to the browser as to the type of data that might
    be entered by the user while editing the element or its contents.

- list (string; optional):
    Identifies a list of pre-defined options to suggest to the user.
    The value must be the id of a <datalist> element in the same
    document. The browser displays only options that are valid values
    for this input element. This attribute is ignored when the type
    attribute's value is hidden, checkbox, radio, file, or a button
    type.

- max (string | number; optional):
    The maximum (numeric or date-time) value for this item, which must
    not be less than its minimum (min attribute) value.

- maxlength (string | number; optional):
    If the value of the type attribute is text, email, search,
    password, tel, or url, this attribute specifies the maximum number
    of characters (in UTF-16 code units) that the user can enter. For
    other control types, it is ignored. It can exceed the value of the
    size attribute. If it is not specified, the user can enter an
    unlimited number of characters. Specifying a negative number
    results in the default behavior (i.e. the user can enter an
    unlimited number of characters). The constraint is evaluated only
    when the value of the attribute has been changed.

- min (string | number; optional):
    The minimum (numeric or date-time) value for this item, which must
    not be greater than its maximum (max attribute) value.

- minlength (string | number; optional):
    If the value of the type attribute is text, email, search,
    password, tel, or url, this attribute specifies the minimum number
    of characters (in Unicode code points) that the user can enter.
    For other control types, it is ignored.

- required (a value equal to: 'required', 'REQUIRED' | boolean; optional):
    This attribute specifies that the user must fill in a value before
    submitting a form. It cannot be used when the type attribute is
    hidden, image, or a button type (submit, reset, or button). The
    :optional and :required CSS pseudo-classes will be applied to the
    field as appropriate. required is an HTML boolean attribute - it
    is enabled by a boolean or 'required'. Alternative capitalizations
    `REQUIRED` are also acccepted.

- readonly (boolean | a value equal to: 'readOnly', 'readonly', 'READONLY'; optional):
    Indicates whether the element can be edited.

- name (string; optional):
    The name of the control, which is submitted with the form data.

- pattern (string; optional):
    A regular expression that the control's value is checked against.
    The pattern must match the entire value, not just some subset. Use
    the title attribute to describe the pattern to help the user. This
    attribute applies when the value of the type attribute is text,
    search, tel, url, email, or password, otherwise it is ignored. The
    regular expression language is the same as JavaScript RegExp
    algorithm, with the 'u' parameter that makes it treat the pattern
    as a sequence of unicode code points. The pattern is not
    surrounded by forward slashes.

- tabindex (string; optional):
    Overrides the browser's default tab order and follows the one
    specified instead.

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
    to apply to the Input.

- tabIndex (string; optional):
    **DEPRECATED** Use `tabindex` instead.  Overrides the browser's
    default tab order and follows the one specified instead.

- maxLength (string | number; optional):
    **DEPRECATED** Use `maxlength` instead.  If the value of the type
    attribute is text, email, search, password, tel, or url, this
    attribute specifies the maximum number of characters (in UTF-16
    code units) that the user can enter. For other control types, it
    is ignored. It can exceed the value of the size attribute. If it
    is not specified, the user can enter an unlimited number of
    characters. Specifying a negative number results in the default
    behavior (i.e. the user can enter an unlimited number of
    characters). The constraint is evaluated only when the value of
    the attribute has been changed.

- minLength (string | number; optional):
    **DEPRECATED** Use `minlength` instead.  If the value of the type
    attribute is text, email, search, password, tel, or url, this
    attribute specifies the minimum number of characters (in Unicode
    code points) that the user can enter. For other control types, it
    is ignored.

- inputMode (a value equal to: 'verbatim', 'latin', 'latin-name', 'latin-prose', 'full-width-latin', 'kana', 'katakana', 'numeric', 'tel', 'email', 'url'; optional):
    **DEPRECATED** Use `inputmode` instead.  Provides a hint to the
    browser as to the type of data that might be entered by the user
    while editing the element or its contents.

- autoComplete (string; optional):
    **DEPRECATED** Use `autocomplete` instead.  This attribute
    indicates whether the value of the control can be automatically
    completed by the browser.

- autoFocus (a value equal to: 'autoFocus', 'autofocus', 'AUTOFOCUS' | boolean; optional):
    **DEPRECATED** Use `autofocus` instead.  The element should be
    automatically focused after the page loaded. autoFocus is an HTML
    boolean attribute - it is enabled by a boolean or 'autoFocus'.
    Alternative capitalizations `autofocus` & `AUTOFOCUS` are also
    acccepted."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Input'

    _explicitize_dash_init = True

    def __init__(
        self,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        value: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        n_submit: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        n_blur: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        size: typing.Optional[str] = None,
        valid: typing.Optional[bool] = None,
        invalid: typing.Optional[bool] = None,
        plaintext: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        type: typing.Optional[Literal["text", "number", "password", "email", "range", "search", "tel", "url", "hidden", "time"]] = None,
        step: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        disabled: typing.Optional[bool] = None,
        placeholder: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        debounce: typing.Optional[typing.Union[bool, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        html_size: typing.Optional[str] = None,
        autocomplete: typing.Optional[str] = None,
        autofocus: typing.Optional[typing.Union[Literal["autoFocus", "autofocus", "AUTOFOCUS"], bool]] = None,
        inputmode: typing.Optional[Literal["verbatim", "latin", "latin-name", "latin-prose", "full-width-latin", "kana", "katakana", "numeric", "tel", "email", "url"]] = None,
        list: typing.Optional[str] = None,
        max: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        maxlength: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        min: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        minlength: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        required: typing.Optional[typing.Union[Literal["required", "REQUIRED"], bool]] = None,
        readonly: typing.Optional[typing.Union[bool, Literal["readOnly", "readonly", "READONLY"]]] = None,
        name: typing.Optional[str] = None,
        pattern: typing.Optional[str] = None,
        tabindex: typing.Optional[str] = None,
        persistence: typing.Optional[typing.Union[bool, str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persisted_props: typing.Optional[typing.Sequence[Literal["value"]]] = None,
        persistence_type: typing.Optional[Literal["local", "session", "memory"]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        tabIndex: typing.Optional[str] = None,
        maxLength: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        minLength: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        inputMode: typing.Optional[Literal["verbatim", "latin", "latin-name", "latin-prose", "full-width-latin", "kana", "katakana", "numeric", "tel", "email", "url"]] = None,
        autoComplete: typing.Optional[str] = None,
        autoFocus: typing.Optional[typing.Union[Literal["autoFocus", "autofocus", "AUTOFOCUS"], bool]] = None,
        **kwargs
    ):
        self._prop_names = ['id', 'value', 'n_submit', 'n_blur', 'size', 'valid', 'invalid', 'plaintext', 'style', 'class_name', 'type', 'step', 'disabled', 'placeholder', 'debounce', 'html_size', 'autocomplete', 'autofocus', 'inputmode', 'list', 'max', 'maxlength', 'min', 'minlength', 'required', 'readonly', 'name', 'pattern', 'tabindex', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className', 'tabIndex', 'maxLength', 'minLength', 'inputMode', 'autoComplete', 'autoFocus']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'value', 'n_submit', 'n_blur', 'size', 'valid', 'invalid', 'plaintext', 'style', 'class_name', 'type', 'step', 'disabled', 'placeholder', 'debounce', 'html_size', 'autocomplete', 'autofocus', 'inputmode', 'list', 'max', 'maxlength', 'min', 'minlength', 'required', 'readonly', 'name', 'pattern', 'tabindex', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className', 'tabIndex', 'maxLength', 'minLength', 'inputMode', 'autoComplete', 'autoFocus']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        super(Input, self).__init__(**args)
