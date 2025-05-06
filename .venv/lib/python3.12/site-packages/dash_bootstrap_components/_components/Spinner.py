# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Spinner(Component):
    """A Spinner component.
Render Bootstrap style loading spinners using only CSS.

This component can be used standalone to render a loading spinner, or it can
be used like `dash_core_components.Loading` by giving it children. In the
latter case the chosen spinner will display while the children are loading.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this Spinner.

- id (string; optional):
    The ID of the Spinner.

- color (string; optional):
    Sets the color of the Spinner. Main options are Bootstrap
    contextual colors: primary, secondary, success, info, warning,
    danger, light, dark, body, muted, white-50, black-50. You can also
    specify any valid CSS color of your choice (e.g. a hex code, a
    decimal code or a CSS color name)  If not specified will default
    to text colour.

- type (string; default 'border'):
    The type of spinner. Options 'border' and 'grow'. Default
    'border'.

- size (string; optional):
    The spinner size. Options are 'sm', and 'md'.

- fullscreen (boolean; optional):
    Boolean that determines if the loading spinner will be displayed
    full-screen or not.

- delay_hide (number; default 0):
    When using the Spinner as a loading spinner, add a time delay (in
    ms) to the spinner being removed to prevent flickering.

- delay_show (number; default 0):
    When using the Spinner as a loading spinner, add a time delay (in
    ms) to the spinner being shown after the component starts loading.

- show_initially (boolean; default True):
    Whether the Spinner should show on app start-up before the loading
    state has been determined. Default True.

- spinner_style (dict; optional):
    Inline CSS styles to apply to the Spinner.

- spinner_class_name (string; optional):
    CSS class names to apply to the Spinner.

- fullscreen_style (dict; optional):
    Defines CSS styles for the container when fullscreen=True.

- fullscreen_class_name (string; optional):
    Additional CSS classes to apply to the Spinner when
    fullscreen=True.

- display (a value equal to: 'auto', 'show', 'hide'; optional):
    Setting display to  \"show\" or \"hide\"  will override the
    loading state coming from dash-renderer.

- target_components (dict with strings as keys and values of type string | list of strings; optional):
    Specify component and prop to trigger showing the loading spinner
    example: `{\"output-container\": \"children\", \"grid\":
    [\"rowData\", \"columnDefs]}`.

- fullscreenClassName (string; optional):
    **DEPRECATED** Use `fullscreen_class_name` instead.  Additional
    CSS classes to apply to the Spinner when fullscreen=True.

- spinnerClassName (string; optional):
    **DEPRECATED** Use `spinner_class_name` instead.  CSS class names
    to apply to the spinner."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Spinner'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        color: typing.Optional[str] = None,
        type: typing.Optional[str] = None,
        size: typing.Optional[str] = None,
        fullscreen: typing.Optional[bool] = None,
        delay_hide: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        delay_show: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        show_initially: typing.Optional[bool] = None,
        spinner_style: typing.Optional[dict] = None,
        spinner_class_name: typing.Optional[str] = None,
        fullscreen_style: typing.Optional[dict] = None,
        fullscreen_class_name: typing.Optional[str] = None,
        display: typing.Optional[Literal["auto", "show", "hide"]] = None,
        target_components: typing.Optional[typing.Dict[typing.Union[str, float, int], typing.Union[str, typing.Sequence[str]]]] = None,
        fullscreenClassName: typing.Optional[str] = None,
        spinnerClassName: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'color', 'type', 'size', 'fullscreen', 'delay_hide', 'delay_show', 'show_initially', 'spinner_style', 'spinner_class_name', 'fullscreen_style', 'fullscreen_class_name', 'display', 'target_components', 'fullscreenClassName', 'spinnerClassName']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'color', 'type', 'size', 'fullscreen', 'delay_hide', 'delay_show', 'show_initially', 'spinner_style', 'spinner_class_name', 'fullscreen_style', 'fullscreen_class_name', 'display', 'target_components', 'fullscreenClassName', 'spinnerClassName']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Spinner, self).__init__(children=children, **args)
