# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Placeholder(Component):
    """A Placeholder component.
Use loading Placeholders for your components or pages to indicate
something may still be loading.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Placeholder.

- id (string; optional):
    The ID of the Placeholder.

- animation (a value equal to: 'glow', 'wave'; optional):
    Changes the animation of the Placeholder.

- color (string; optional):
    Background color, options: primary, secondary, success, info,
    warning, danger, light, dark.

- size (a value equal to: 'xs', 'sm', 'lg'; optional):
    Placeholder size variations. Only valid when `button=False`.

- button (boolean; default False):
    Show as a button shape.

- delay_hide (number; default 0):
    When using the placeholder as a loading placeholder, add a time
    delay (in ms) to the placeholder being removed to prevent
    flickering.

- delay_show (number; default 0):
    When using the placeholder as a loading placeholder, add a time
    delay (in ms) to the placeholder being shown after the lcomponent
    starts loading.

- show_initially (boolean; default True):
    Whether the Placeholder should show on app start-up before the
    loading state has been determined. Default True.

- class_name (string; optional):
    Additional CSS classes to apply to the Placeholder.

- xs (number; optional):
    Specify placeholder behaviour on an extra small screen.  Valid
    arguments are boolean, an integer in the range 1-12 inclusive. See
    the documentation for more details.

- sm (number; optional):
    Specify placeholder behaviour on a small screen.  Valid arguments
    are boolean, an integer in the range 1-12 inclusive. See the
    documentation for more details.

- md (number; optional):
    Specify placeholder behaviour on a medium screen.  Valid arguments
    are boolean, an integer in the range 1-12 inclusive. See the
    documentation for more details.

- lg (number; optional):
    Specify placeholder behaviour on a large screen.  Valid arguments
    are boolean, an integer in the range 1-12 inclusive. See the
    documentation for more details.

- xl (number; optional):
    Specify placeholder behaviour on an extra large screen.  Valid
    arguments are boolean, an integer in the range 1-12 inclusive. See
    the documentation for more details.

- xxl (number; optional):
    Specify placeholder behaviour on an extra extra large screen.
    Valid arguments are boolean, an integer in the range 1-12
    inclusive. See the documentation for more details.

- target_components (dict with strings as keys and values of type string | list of strings; optional):
    Specify component and prop to trigger showing the placeholder.
    Example: `{\"output-container\": \"children\", \"grid\":
    [\"rowData\", \"columnDefs]}`.

- display (a value equal to: 'auto', 'show', 'hide'; default 'auto'):
    Setting display to  \"show\" or \"hide\"  will override the
    loading state coming from dash-renderer.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Placeholder."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Placeholder'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        animation: typing.Optional[Literal["glow", "wave"]] = None,
        color: typing.Optional[str] = None,
        size: typing.Optional[Literal["xs", "sm", "lg"]] = None,
        button: typing.Optional[bool] = None,
        delay_hide: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        delay_show: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        show_initially: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        xs: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        sm: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        md: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        lg: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        xl: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        xxl: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        target_components: typing.Optional[typing.Dict[typing.Union[str, float, int], typing.Union[str, typing.Sequence[str]]]] = None,
        display: typing.Optional[Literal["auto", "show", "hide"]] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'animation', 'color', 'size', 'button', 'delay_hide', 'delay_show', 'show_initially', 'style', 'class_name', 'xs', 'sm', 'md', 'lg', 'xl', 'xxl', 'target_components', 'display', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'animation', 'color', 'size', 'button', 'delay_hide', 'delay_show', 'show_initially', 'style', 'class_name', 'xs', 'sm', 'md', 'lg', 'xl', 'xxl', 'target_components', 'display', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Placeholder, self).__init__(children=children, **args)
