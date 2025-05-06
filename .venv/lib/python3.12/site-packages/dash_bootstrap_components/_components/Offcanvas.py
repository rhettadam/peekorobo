# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Offcanvas(Component):
    """An Offcanvas component.
Create a toggleable hidden sidebar using the Offcanvas component.
Toggle the visibility with the `is_open` prop.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Offcanvas.

- id (string; optional):
    The ID of the Offcanvas.

- is_open (boolean; default False):
    Whether offcanvas is currently open.

- title (a list of or a singular dash component, string or number; optional):
    The header title.

- placement (a value equal to: 'start', 'end', 'top', 'bottom'; optional):
    Which side of the viewport the offcanvas will appear from.

- backdrop (boolean | a value equal to: 'static'; default True):
    Includes an offcanvas-backdrop element. Alternatively, specify
    'static' for a backdrop which doesn't close the modal on click.

- close_button (boolean; default True):
    Specify whether the Offcanvas should contain a close button in the
    header.

- keyboard (boolean; optional):
    If True, the offcanvas will close when the escape key is pressed.

- scrollable (boolean; optional):
    Allow body scrolling while offcanvas is open.

- class_name (string; optional):
    Additional CSS classes to apply to the Offcanvas.

- backdrop_class_name (string; optional):
    CSS class to apply to the backdrop.

- autofocus (boolean; optional):
    Puts the focus on the offcanvas when initialized.

- labelledby (string; optional):
    The ARIA labelledby attribute.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Offcanvas.

- backdropClassName (string; optional):
    **DEPRECATED** Use `backdrop_class_name` instead.  CSS class to
    apply to the backdrop.

- autoFocus (boolean; optional):
    **DEPRECATED** Use `autofocus` instead.          Puts the focus on
    the modal when initialized.

- labelledBy (string; optional):
    **DEPRECATED** Use `labelledby` instead.  The ARIA labelledby
    attribute."""
    _children_props = ['title']
    _base_nodes = ['title', 'children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Offcanvas'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        is_open: typing.Optional[bool] = None,
        title: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        placement: typing.Optional[Literal["start", "end", "top", "bottom"]] = None,
        backdrop: typing.Optional[typing.Union[bool, Literal["static"]]] = None,
        close_button: typing.Optional[bool] = None,
        keyboard: typing.Optional[bool] = None,
        scrollable: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        backdrop_class_name: typing.Optional[str] = None,
        autofocus: typing.Optional[bool] = None,
        labelledby: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        backdropClassName: typing.Optional[str] = None,
        autoFocus: typing.Optional[bool] = None,
        labelledBy: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'is_open', 'title', 'placement', 'backdrop', 'close_button', 'keyboard', 'scrollable', 'style', 'class_name', 'backdrop_class_name', 'autofocus', 'labelledby', 'className', 'backdropClassName', 'autoFocus', 'labelledBy']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'is_open', 'title', 'placement', 'backdrop', 'close_button', 'keyboard', 'scrollable', 'style', 'class_name', 'backdrop_class_name', 'autofocus', 'labelledby', 'className', 'backdropClassName', 'autoFocus', 'labelledBy']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Offcanvas, self).__init__(children=children, **args)
