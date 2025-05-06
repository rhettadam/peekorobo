# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Accordion(Component):
    """An Accordion component.
A self contained Accordion component. Build up the children using the
AccordionItem component.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Accordion.

- id (string; optional):
    The ID of the Accordion.

- active_item (string | list of strings; optional):
    The item_id of the currently active item. If item_id has not been
    specified for the active item, this will default to item-i, where
    i is the index (starting from 0) of the item.  If
    `always_open=True`, then active_item should be a list item_ids of
    all the currently open AccordionItems.

- always_open (boolean; default False):
    If True, multiple items can be expanded at once.

- start_collapsed (boolean; default False):
    If True, all items will start collapsed.

- flush (boolean; optional):
    If True the Accordion will be rendered edge-to-edge within its
    parent container.

- class_name (string; optional):
    Additional CSS class to apply to the Accordion.

- persistence (boolean | string | number; optional):
    Used to allow user interactions to be persisted when the page is
    refreshed. See https://dash.plotly.com/persistence for more
    details.

- persisted_props (list of a value equal to: 'active_item's; optional):
    Properties to persist. Since only `active_item` is supported, this
    prop can normally be ignored.

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
    **DEPRECATED** Use `class_name` instead.  Additional CSS class to
    apply to the Accordion."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Accordion'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        active_item: typing.Optional[typing.Union[str, typing.Sequence[str]]] = None,
        always_open: typing.Optional[bool] = None,
        start_collapsed: typing.Optional[bool] = None,
        flush: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        persistence: typing.Optional[typing.Union[bool, str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persisted_props: typing.Optional[typing.Sequence[Literal["active_item"]]] = None,
        persistence_type: typing.Optional[Literal["local", "session", "memory"]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'active_item', 'always_open', 'start_collapsed', 'flush', 'style', 'class_name', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'active_item', 'always_open', 'start_collapsed', 'flush', 'style', 'class_name', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Accordion, self).__init__(children=children, **args)
