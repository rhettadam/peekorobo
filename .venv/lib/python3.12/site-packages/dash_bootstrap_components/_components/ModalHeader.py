# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class ModalHeader(Component):
    """A ModalHeader component.
Add a header to any Modal.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this ModalHeader.

- id (string; optional):
    The ID of the ModalHeader.

- close_button (boolean; default True):
    Add a close button to the header that can be used to close the
    modal.

- class_name (string; optional):
    Additional CSS classes to apply to the ModalHeader.

- tag (string; optional):
    HTML tag to use for the ModalHeader, default: div.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the ModalHeader."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'ModalHeader'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        close_button: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        tag: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'close_button', 'style', 'class_name', 'tag', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'close_button', 'style', 'class_name', 'tag', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(ModalHeader, self).__init__(children=children, **args)
