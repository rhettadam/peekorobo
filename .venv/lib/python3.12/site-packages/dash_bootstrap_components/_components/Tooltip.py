# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Tooltip(Component):
    """A Tooltip component.
A component for adding tooltips to any element, no callbacks required!

Simply add the Tooltip to you layout, and give it a target (id of a
component to which the tooltip should be attached)

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this Tooltip.

- id (string; optional):
    The ID of the Tooltip.

- target (string | dict; optional):
    The id of the element to attach the tooltip to.

- is_open (boolean; optional):
    Whether the Tooltip is open or not.

- trigger (string; default 'hover focus'):
    Space separated list of triggers (e.g. \"click hover focus
    legacy\"). These specify ways in which the target component can
    toggle the tooltip. If omitted you must toggle the tooltip
    yourself using callbacks. Options are: - \"click\": toggles the
    popover when the target is clicked. - \"hover\": toggles the
    popover when the target is hovered over with the cursor. -
    \"focus\": toggles the popover when the target receives focus -
    \"legacy\": toggles the popover when the target is clicked, but
    will also dismiss the popover when the user clicks outside of the
    popover.  Default is \"hover focus\".

- placement (a value equal to: 'auto', 'auto-start', 'auto-end', 'top', 'top-start', 'top-end', 'right', 'right-start', 'right-end', 'bottom', 'bottom-start', 'bottom-end', 'left', 'left-start', 'left-end'; default 'auto'):
    How to place the tooltip.

- delay (dict; default {show: 0, hide: 50}):
    Control the delay of hide and show events.

    `delay` is a dict with keys:

    - show (number; optional)

    - hide (number; optional)

- flip (boolean; default True):
    Whether to flip the direction of the popover if too close to the
    container edge, default True.

- autohide (boolean; default True):
    Optionally hide tooltip when hovering over tooltip content -
    default True.

- fade (boolean; default True):
    If True, a fade animation will be applied when `is_open` is
    toggled. If False the Alert will simply appear and disappear.

- class_name (string; optional):
    Additional CSS classes to apply to the Tooltip.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Tooltip."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Tooltip'
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
        delay: typing.Optional["Delay"] = None,
        flip: typing.Optional[bool] = None,
        autohide: typing.Optional[bool] = None,
        fade: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'target', 'is_open', 'trigger', 'placement', 'delay', 'flip', 'autohide', 'fade', 'style', 'class_name', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'target', 'is_open', 'trigger', 'placement', 'delay', 'flip', 'autohide', 'fade', 'style', 'class_name', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Tooltip, self).__init__(children=children, **args)
