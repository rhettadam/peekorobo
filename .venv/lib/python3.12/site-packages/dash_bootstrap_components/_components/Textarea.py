# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Textarea(Component):
    """A Textarea component.
A basic HTML textarea for entering multiline text based on the corresponding
component in dash-core-components

Keyword arguments:

- id (string; optional):
    The ID of the Textarea.

- value (string; default ''):
    The value of the textarea.

- n_blur (number; default 0):
    Number of times the input lost focus.

- n_submit (number; default 0):
    Number of times the `Enter` key was pressed while the textarea had
    focus. Only updates if submit_on_enter is True.

- n_clicks (number; default 0):
    The number of times the TextArea has been clicked.

- valid (boolean; optional):
    Apply valid style to the Textarea for feedback purposes. This will
    cause any FormFeedback in the enclosing div with valid=True to
    display.

- invalid (boolean; optional):
    Apply invalid style to the Textarea for feedback purposes. This
    will cause any FormFeedback in the enclosing div with valid=False
    to display.

- placeholder (string; optional):
    Provides a hint to the user of what can be entered in the field.

- size (string; optional):
    Set the size of the Textarea, valid options are 'sm', 'md', or
    'lg'.

- class_name (string; optional):
    Additional CSS classes to apply to the Textarea.

- accesskey (string; optional):
    Defines a keyboard shortcut to activate or add focus to the
    element.

- autofocus (string; optional):
    The element should be automatically focused after the page loaded.

- contenteditable (string | number; optional):
    Indicates whether the element's content is editable.

- contextmenu (string; optional):
    Defines the ID of a <menu> element which will serve as the
    element's context menu.

- cols (string | number; optional):
    Defines the number of columns in a textarea.

- dir (string; optional):
    Defines the text direction. Allowed values are ltr (Left-To-Right)
    or rtl (Right-To-Left).

- disabled (string | boolean; optional):
    Indicates whether the user can interact with the element.

- draggable (a value equal to: 'true', 'false' | boolean; optional):
    Defines whether the element can be dragged.

- form (string; optional):
    Indicates the form that is the owner of the element.

- hidden (string; optional):
    Prevents rendering of given element, while keeping child elements,
    e.g. script elements, active.

- lang (string; optional):
    Defines the language used in the element.

- maxlength (string | number; optional):
    Defines the maximum number of characters allowed in the element.

- minlength (string | number; optional):
    Defines the minimum number of characters allowed in the element.

- name (string; optional):
    Name of the element. For example used by the server to identify
    the fields in form submits.

- readonly (boolean | a value equal to: 'readOnly', 'readonly', 'READONLY'; optional):
    Indicates whether the element can be edited.

- required (a value equal to: 'required', 'REQUIRED' | boolean; optional):
    This attribute specifies that the user must fill in a value before
    submitting a form. It cannot be used when the type attribute is
    hidden, image, or a button type (submit, reset, or button). The
    :optional and :required CSS pseudo-classes will be applied to the
    field as appropriate. required is an HTML boolean attribute - it
    is enabled by a boolean or 'required'. Alternative capitalizations
    `REQUIRED` are also acccepted.

- rows (string | number; optional):
    Defines the number of rows in a text area.

- spellcheck (a value equal to: 'true', 'false' | boolean; optional):
    Indicates whether spell checking is allowed for the element.

- tabindex (string | number; optional):
    Overrides the browser's default tab order and follows the one
    specified instead.

- title (string; optional):
    Text to be displayed in a tooltip when hovering over the element.

- wrap (string; optional):
    Indicates whether the text should be wrapped.

- submit_on_enter (boolean; default True):
    Whether or not the form should increment the n_submit prop when
    enter key is pressed. If True, use shift + enter to create a
    newline. Default: True.

- debounce (boolean | number; default False):
    If True, changes to input will be sent back to the Dash server
    only on enter or when losing focus. If it's False, it will sent
    the value back on every change. If debounce is a number, the value
    will be sent to the server only after the user has stopped typing
    for that number of milliseconds.

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
    to apply to the Textarea.

- accessKey (string; optional):
    **DEPRECATED** Use `accesskey` instead.  Defines a keyboard
    shortcut to activate or add focus to the element.

- autoFocus (string; optional):
    **DEPRECATED** Use `autofocus` instead.  The element should be
    automatically focused after the page loaded.

- contentEditable (string | number; optional):
    **DEPRECATED** Use `contenteditable` instead.  Indicates whether
    the element's content is editable.

- contextMenu (string; optional):
    **DEPRECATED** Use `contextmenu` instead.  Defines the ID of a
    <menu> element which will serve as the element's context menu.

- maxLength (string | number; optional):
    **DEPRECATED** Use `maxlength` instead.  Defines the maximum
    number of characters allowed in the element.

- minLength (string | number; optional):
    **DEPRECATED** Use `minlength` instead.  Defines the minimum
    number of characters allowed in the element.

- readOnly (boolean | a value equal to: 'readOnly', 'readonly', 'READONLY'; optional):
    **DEPRECATED** Use `readonly` instead.  Indicates whether the
    element can be edited.

- spellCheck (a value equal to: 'true', 'false' | boolean; optional):
    **DEPRECATED** Use `spellcheck` instead.  Indicates whether spell
    checking is allowed for the element.

- tabIndex (string | number; optional):
    **DEPRECATED** Use `tabindex` instead.  Overrides the browser's
    default tab order and follows the one specified instead."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Textarea'

    _explicitize_dash_init = True

    def __init__(
        self,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        value: typing.Optional[str] = None,
        n_blur: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        n_submit: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        n_clicks: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        valid: typing.Optional[bool] = None,
        invalid: typing.Optional[bool] = None,
        placeholder: typing.Optional[str] = None,
        size: typing.Optional[str] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        accesskey: typing.Optional[str] = None,
        autofocus: typing.Optional[str] = None,
        contenteditable: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        contextmenu: typing.Optional[str] = None,
        cols: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        dir: typing.Optional[str] = None,
        disabled: typing.Optional[typing.Union[str, bool]] = None,
        draggable: typing.Optional[typing.Union[Literal["true", "false"], bool]] = None,
        form: typing.Optional[str] = None,
        hidden: typing.Optional[str] = None,
        lang: typing.Optional[str] = None,
        maxlength: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        minlength: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        name: typing.Optional[str] = None,
        readonly: typing.Optional[typing.Union[bool, Literal["readOnly", "readonly", "READONLY"]]] = None,
        required: typing.Optional[typing.Union[Literal["required", "REQUIRED"], bool]] = None,
        rows: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        spellcheck: typing.Optional[typing.Union[Literal["true", "false"], bool]] = None,
        tabindex: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        title: typing.Optional[str] = None,
        wrap: typing.Optional[str] = None,
        submit_on_enter: typing.Optional[bool] = None,
        debounce: typing.Optional[typing.Union[bool, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persistence: typing.Optional[typing.Union[bool, str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persisted_props: typing.Optional[typing.Sequence[Literal["value"]]] = None,
        persistence_type: typing.Optional[Literal["local", "session", "memory"]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        accessKey: typing.Optional[str] = None,
        autoFocus: typing.Optional[str] = None,
        contentEditable: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        contextMenu: typing.Optional[str] = None,
        maxLength: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        minLength: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        readOnly: typing.Optional[typing.Union[bool, Literal["readOnly", "readonly", "READONLY"]]] = None,
        spellCheck: typing.Optional[typing.Union[Literal["true", "false"], bool]] = None,
        tabIndex: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        **kwargs
    ):
        self._prop_names = ['id', 'value', 'n_blur', 'n_submit', 'n_clicks', 'valid', 'invalid', 'placeholder', 'size', 'style', 'class_name', 'accesskey', 'autofocus', 'contenteditable', 'contextmenu', 'cols', 'dir', 'disabled', 'draggable', 'form', 'hidden', 'lang', 'maxlength', 'minlength', 'name', 'readonly', 'required', 'rows', 'spellcheck', 'tabindex', 'title', 'wrap', 'submit_on_enter', 'debounce', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className', 'accessKey', 'autoFocus', 'contentEditable', 'contextMenu', 'maxLength', 'minLength', 'readOnly', 'spellCheck', 'tabIndex']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'value', 'n_blur', 'n_submit', 'n_clicks', 'valid', 'invalid', 'placeholder', 'size', 'style', 'class_name', 'accesskey', 'autofocus', 'contenteditable', 'contextmenu', 'cols', 'dir', 'disabled', 'draggable', 'form', 'hidden', 'lang', 'maxlength', 'minlength', 'name', 'readonly', 'required', 'rows', 'spellcheck', 'tabindex', 'title', 'wrap', 'submit_on_enter', 'debounce', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className', 'accessKey', 'autoFocus', 'contentEditable', 'contextMenu', 'maxLength', 'minLength', 'readOnly', 'spellCheck', 'tabIndex']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        super(Textarea, self).__init__(**args)
