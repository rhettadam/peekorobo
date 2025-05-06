# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class DropdownMenu(Component):
    """A DropdownMenu component.
DropdownMenu creates an overlay useful for grouping together links and other
content to organise navigation or other interactive elements.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the DropdownMenu.

- id (string; optional):
    The ID of the DropdownMenu.

- label (a list of or a singular dash component, string or number; optional):
    Label for the DropdownMenu toggle.

- color (string; optional):
    Set the color of the DropdownMenu toggle. Available options are:
    'primary', 'secondary', 'success', 'warning', 'danger', 'info',
    'link' or any valid CSS color of your choice (e.g. a hex code, a
    decimal code or a CSS color name).  Default: 'primary'.

- direction (a value equal to: 'down', 'start', 'up', 'end'; optional):
    Direction in which to expand the DropdownMenu. Options are 'down',
    'start', 'up' and 'end'.  Default: 'down'.

- size (a value equal to: 'sm', 'md', 'lg'; optional):
    Size of the DropdownMenu. 'sm' corresponds to small, 'md' to
    medium and 'lg' to large.

- disabled (boolean; default False):
    Disable the dropdown.

- class_name (string; optional):
    Additional CSS classes to apply to the DropdownMenu.

- align_end (boolean; optional):
    Align the DropdownMenu along the right side of its parent.
    Default: False.

- in_navbar (boolean; optional):
    Set this to True if the DropdownMenu is inside a navbar. Default:
    False.

- nav (boolean; optional):
    Set this to True if the DropdownMenu is inside a nav for styling
    consistent with other nav items. Default: False.

- caret (boolean; default True):
    Add a caret to the DropdownMenu toggle. Default: True.

- menu_variant (a value equal to: 'light', 'dark'; default 'light'):
    Set `menu_variant=\"dark\"` to create a dark-mode drop down
    instead.

- group (boolean; optional):
    Set group to True if the DropdownMenu is inside a ButtonGroup.

- toggle_style (dict; optional):
    Additional inline CSS styles to apply to the DropdownMenu toggle.

- toggle_class_name (string; optional):
    Additional CSS classes to apply to the DropdownMenu.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the DropdownMenu.

- toggleClassName (string; optional):
    **DEPRECATED** Use `toggle_class_name` instead.  Additional CSS
    classes to apply to the DropdownMenu. The classes specified with
    this prop will be applied to the DropdownMenu toggle."""
    _children_props = ['label']
    _base_nodes = ['label', 'children']
    _namespace = 'dash_bootstrap_components'
    _type = 'DropdownMenu'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        label: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        color: typing.Optional[str] = None,
        direction: typing.Optional[Literal["down", "start", "up", "end"]] = None,
        size: typing.Optional[Literal["sm", "md", "lg"]] = None,
        disabled: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        align_end: typing.Optional[bool] = None,
        in_navbar: typing.Optional[bool] = None,
        nav: typing.Optional[bool] = None,
        caret: typing.Optional[bool] = None,
        menu_variant: typing.Optional[Literal["light", "dark"]] = None,
        group: typing.Optional[bool] = None,
        toggle_style: typing.Optional[dict] = None,
        toggle_class_name: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        toggleClassName: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'label', 'color', 'direction', 'size', 'disabled', 'style', 'class_name', 'align_end', 'in_navbar', 'nav', 'caret', 'menu_variant', 'group', 'toggle_style', 'toggle_class_name', 'key', 'className', 'toggleClassName']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'label', 'color', 'direction', 'size', 'disabled', 'style', 'class_name', 'align_end', 'in_navbar', 'nav', 'caret', 'menu_variant', 'group', 'toggle_style', 'toggle_class_name', 'key', 'className', 'toggleClassName']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(DropdownMenu, self).__init__(children=children, **args)
