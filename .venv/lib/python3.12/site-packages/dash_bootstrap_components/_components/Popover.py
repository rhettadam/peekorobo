# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Popover(Component):
    """A Popover component.
Popover creates a toggleable overlay that can be used to provide additional
information or content to users without having to load a new page or open a new
window.

Use the `PopoverHeader` and `PopoverBody` components to control the layout of the
children.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this Popover.

- id (string; optional):
    The ID of the Popover.

- target (string | dict; optional):
    ID of the component to attach the Popover to.

- is_open (boolean; optional):
    Whether the Popover is open or not.

- trigger (string; optional):
    Space separated list of triggers (e.g. \"click hover focus
    legacy\"). These specify ways in which the target Popover can
    toggle the Popover. If not specified you must toggle the Popover
    yourself using callbacks. Options are: - \"click\": toggles the
    Popover when the target is clicked. - \"hover\": toggles the
    Popover when the target is hovered over with the cursor. -
    \"focus\": toggles the Popover when the target receives focus -
    \"legacy\": toggles the Popover when the target is clicked, but
    will also dismiss the Popover when the user clicks outside of the
    Popover.

- placement (a value equal to: 'auto', 'auto-start', 'auto-end', 'top', 'top-start', 'top-end', 'right', 'right-start', 'right-end', 'bottom', 'bottom-start', 'bottom-end', 'left', 'left-start', 'left-end'; default 'right'):
    Specify Popover placement.

- hide_arrow (boolean; optional):
    Hide Popover arrow.

- delay (dict; default {show: 0, hide: 50}):
    Optionally override show/hide delays.

    `delay` is a dict with keys:

    - show (number; optional)

    - hide (number; optional) | number

- offset (string | number; optional):
    Offset of the Popover relative to its target. The offset can be
    passed as a comma separated pair of values e.g. \"0,8\", where the
    first number, skidding, displaces the Popover along the reference
    element. The second number, distance, displaces the Popover away
    from, or toward, the reference element in the direction of its
    placement. A positive number displaces it further away, while a
    negative number lets it overlap the reference. See
    https://popper.js.org/docs/v2/modifiers/offset/ for more info.
    Alternatively, you can provide just a single 'distance' number
    e.g. 8 to displace it horizontally.

- flip (boolean; default True):
    Whether to flip the direction of the Popover if too close to the
    container edge, default True.

- body (boolean; optional):
    When body is `True`, the Popover will render all children in a
    `PopoverBody` automatically.

- autohide (boolean; default False):
    Optionally hide Popover when hovering over content - default
    False.

- class_name (string; optional):
    Additional CSS classes to apply to the Popover.

- persistence (boolean | string | number; optional):
    Used to allow user interactions to be persisted when the page is
    refreshed. See https://dash.plotly.com/persistence for more
    details.

- persisted_props (list of a value equal to: 'is_open's; optional):
    Properties whose user interactions will persist after refreshing
    the Popover or the page. Since only `value` is allowed this prop
    can normally be ignored.

- persistence_type (a value equal to: 'local', 'session', 'memory'; optional):
    Where persisted user changes will be stored: - memory: only kept
    in memory, reset on page refresh. - local: window.localStorage,
    data is kept after the browser quit. - session:
    window.sessionStorage, data is cleared once the browser quit.

- key (string; optional):
    A unique identifier for the Popover, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Popover."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Popover'
    Delay = TypedDict(
        "Delay",
            {
            "show": NotRequired[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]],
            "hide": NotRequired[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]
        }
    )

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        target: typing.Optional[typing.Union[str, dict]] = None,
        is_open: typing.Optional[bool] = None,
        trigger: typing.Optional[str] = None,
        placement: typing.Optional[Literal["auto", "auto-start", "auto-end", "top", "top-start", "top-end", "right", "right-start", "right-end", "bottom", "bottom-start", "bottom-end", "left", "left-start", "left-end"]] = None,
        hide_arrow: typing.Optional[bool] = None,
        delay: typing.Optional[typing.Union["Delay", typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        offset: typing.Optional[typing.Union[str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        flip: typing.Optional[bool] = None,
        body: typing.Optional[bool] = None,
        autohide: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        persistence: typing.Optional[typing.Union[bool, str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persisted_props: typing.Optional[typing.Sequence[Literal["is_open"]]] = None,
        persistence_type: typing.Optional[Literal["local", "session", "memory"]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'target', 'is_open', 'trigger', 'placement', 'hide_arrow', 'delay', 'offset', 'flip', 'body', 'autohide', 'style', 'class_name', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'target', 'is_open', 'trigger', 'placement', 'hide_arrow', 'delay', 'offset', 'flip', 'body', 'autohide', 'style', 'class_name', 'persistence', 'persisted_props', 'persistence_type', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Popover, self).__init__(children=children, **args)
