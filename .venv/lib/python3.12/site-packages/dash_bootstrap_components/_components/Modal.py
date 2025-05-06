# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Modal(Component):
    """A Modal component.
Create a toggleable dialog using the Modal component. Toggle the visibility with the
`is_open` prop.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Modal.

- id (string; optional):
    The ID of the Modal.

- is_open (boolean; optional):
    Whether modal is currently open.

- centered (boolean; optional):
    If True, vertically center modal on page.

- scrollable (boolean; optional):
    It True, scroll the modal body rather than the entire modal when
    it is too long to all fit on the screen.

- size (string; optional):
    Set the size of the modal. Options sm, lg, xl for small, large or
    extra large sized modals, or leave undefined for default size.

- backdrop (boolean | a value equal to: 'static'; optional):
    Includes a modal-backdrop element. Alternatively, specify 'static'
    for a backdrop which doesn't close the modal on click.

- fullscreen (boolean | a value equal to: 'sm-down', 'md-down', 'lg-down', 'xl-down', 'xxl-down'; optional):
    Renders a fullscreen modal. Specifying a breakpoint will render
    the modal as fullscreen below the breakpoint size.

- keyboard (boolean; optional):
    Close the modal when escape key is pressed.

- fade (boolean; optional):
    Set to False for a modal that simply appears rather than fades
    into view.

- dialog_style (dict; optional):
    Inline CSS styles to apply to the dialog.

- content_style (dict; optional):
    Inline CSS styles to apply to the content.

- backdrop_style (dict; optional):
    Inline CSS styles to apply to the backdrop.

- class_name (string; optional):
    Additional CSS classes to apply to the Modal.

- dialog_class_name (string; optional):
    Additional CSS classes to apply to the modal.

- backdrop_class_name (string; optional):
    Additional CSS classes to apply to the modal-backdrop.

- content_class_name (string; optional):
    Additional CSS classes to apply to the modal content.

- tag (string; optional):
    HTML tag to use for the Modal, default: div.

- autofocus (boolean; optional):
    Puts the focus on the modal when initialized.

- enforceFocus (boolean; optional):
    When True The modal will prevent focus from leaving the Modal
    while open.

- role (string; optional):
    The ARIA role attribute.

- labelledby (string; optional):
    The ARIA labelledby attribute.

- zindex (number | string; optional):
    Set the z-index of the modal. Default 1050.

- dialogStyle (dict; optional):
    **DEPRECATED** Use `dialog_style` instead.  Inline CSS styles to
    apply to the dialog.

- contentStyle (dict; optional):
    **DEPRECATED** Use `content_style` instead.  Inline CSS styles to
    apply to the content.

- backdropStyle (dict; optional):
    **DEPRECATED** Use `backdrop_style` instead.  Inline CSS styles to
    apply to the backdrop.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Modal.

- backdropClassName (string; optional):
    **DEPRECATED** Use `backdrop_class_name` instead.  Additional CSS
    classes to apply to the modal-backdrop.

- contentClassName (string; optional):
    **DEPRECATED** Use `content_class_name` instead.  Additional CSS
    classes to apply to the modal-content.

- dialogClassName (string; optional):
    **DEPRECATED** Use `dialog_class_name` instead.  Additional CSS
    classes to apply to the modal-dialog.

- autoFocus (boolean; optional):
    **DEPRECATED** Use `autofocus` instead.          Puts the focus on
    the modal when initialized.

- labelledBy (string; optional):
    **DEPRECATED** Use `labelledby` instead.  The ARIA labelledby
    attribute.

- zIndex (number | string; optional):
    **DEPRECATED** Use `zindex` instead.  Set the z-index of the
    modal. Default 1050."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Modal'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        is_open: typing.Optional[bool] = None,
        centered: typing.Optional[bool] = None,
        scrollable: typing.Optional[bool] = None,
        size: typing.Optional[str] = None,
        backdrop: typing.Optional[typing.Union[bool, Literal["static"]]] = None,
        fullscreen: typing.Optional[typing.Union[bool, Literal["sm-down", "md-down", "lg-down", "xl-down", "xxl-down"]]] = None,
        keyboard: typing.Optional[bool] = None,
        fade: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        dialog_style: typing.Optional[dict] = None,
        content_style: typing.Optional[dict] = None,
        backdrop_style: typing.Optional[dict] = None,
        class_name: typing.Optional[str] = None,
        dialog_class_name: typing.Optional[str] = None,
        backdrop_class_name: typing.Optional[str] = None,
        content_class_name: typing.Optional[str] = None,
        tag: typing.Optional[str] = None,
        autofocus: typing.Optional[bool] = None,
        enforceFocus: typing.Optional[bool] = None,
        role: typing.Optional[str] = None,
        labelledby: typing.Optional[str] = None,
        zindex: typing.Optional[typing.Union[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex], str]] = None,
        dialogStyle: typing.Optional[dict] = None,
        contentStyle: typing.Optional[dict] = None,
        backdropStyle: typing.Optional[dict] = None,
        className: typing.Optional[str] = None,
        backdropClassName: typing.Optional[str] = None,
        contentClassName: typing.Optional[str] = None,
        dialogClassName: typing.Optional[str] = None,
        autoFocus: typing.Optional[bool] = None,
        labelledBy: typing.Optional[str] = None,
        zIndex: typing.Optional[typing.Union[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex], str]] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'is_open', 'centered', 'scrollable', 'size', 'backdrop', 'fullscreen', 'keyboard', 'fade', 'style', 'dialog_style', 'content_style', 'backdrop_style', 'class_name', 'dialog_class_name', 'backdrop_class_name', 'content_class_name', 'tag', 'autofocus', 'enforceFocus', 'role', 'labelledby', 'zindex', 'dialogStyle', 'contentStyle', 'backdropStyle', 'className', 'backdropClassName', 'contentClassName', 'dialogClassName', 'autoFocus', 'labelledBy', 'zIndex']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'is_open', 'centered', 'scrollable', 'size', 'backdrop', 'fullscreen', 'keyboard', 'fade', 'style', 'dialog_style', 'content_style', 'backdrop_style', 'class_name', 'dialog_class_name', 'backdrop_class_name', 'content_class_name', 'tag', 'autofocus', 'enforceFocus', 'role', 'labelledby', 'zindex', 'dialogStyle', 'contentStyle', 'backdropStyle', 'className', 'backdropClassName', 'contentClassName', 'dialogClassName', 'autoFocus', 'labelledBy', 'zIndex']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Modal, self).__init__(children=children, **args)
