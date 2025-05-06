# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Fade(Component):
    """A Fade component.
Hide or show content with a fading animation. Visibility of the children is
controlled by the `is_open` prop which can be targetted by callbacks.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of the Fade.

- id (string; optional):
    The ID of the Fade.

- is_in (boolean; optional):
    Controls whether the children of the Fade component are currently
    visible or not.

- class_name (string; optional):
    Additional CSS classes to apply to the Fade.

- timeout (dict; optional):
    The duration of the transition, in milliseconds.  You may specify
    a single timeout for all transitions like: `timeout=500` or
    individually like: timeout={'enter': 300, 'exit': 500}.

    `timeout` is a number | dict with keys:

    - enter (number; optional)

    - exit (number; optional)

- appear (boolean; optional):
    Show fade-in animation on initial page load. Default: True.

- enter (boolean; optional):
    Enable or disable enter transitions. Default: True.

- exit (boolean; optional):
    Enable or disable exit transitions. Default: True.

- tag (string; optional):
    HTML tag to use for the fade component. Default: div.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Fade."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Fade'
    Timeout = TypedDict(
        "Timeout",
            {
            "enter": NotRequired[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]],
            "exit": NotRequired[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]
        }
    )

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        is_in: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        timeout: typing.Optional[typing.Union[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex], "Timeout"]] = None,
        appear: typing.Optional[bool] = None,
        enter: typing.Optional[bool] = None,
        exit: typing.Optional[bool] = None,
        tag: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'is_in', 'style', 'class_name', 'timeout', 'appear', 'enter', 'exit', 'tag', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'is_in', 'style', 'class_name', 'timeout', 'appear', 'enter', 'exit', 'tag', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Fade, self).__init__(children=children, **args)
