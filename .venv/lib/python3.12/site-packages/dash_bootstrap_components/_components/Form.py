# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Form(Component):
    """A Form component.
The Form component can be used to organise collections of input components
and apply consistent styling.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    The children of this Form.

- id (string; optional):
    The ID of the Form.

- n_submit (number; default 0):
    Number of times the form was submitted.

- class_name (string; optional):
    Additional CSS classes to apply to the Form.

- action (string; optional):
    The URI of a program that processes the information submitted via
    the form.

- method (a value equal to: 'GET', 'POST'; optional):
    Defines which HTTP method to use when submitting the form. Can be
    GET (default) or POST.

- prevent_default_on_submit (boolean; default True):
    The form calls preventDefault on submit events. If you want form
    data be posted to the endpoint specified by `action` on submit
    events, set prevent_default_on_submit to False. Defaults to True.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Form."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Form'

    _explicitize_dash_init = True

    def __init__(
        self,
        children: typing.Optional[typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        n_submit: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        action: typing.Optional[str] = None,
        method: typing.Optional[Literal["GET", "POST"]] = None,
        prevent_default_on_submit: typing.Optional[bool] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'n_submit', 'style', 'class_name', 'action', 'method', 'prevent_default_on_submit', 'key', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'n_submit', 'style', 'class_name', 'action', 'method', 'prevent_default_on_submit', 'key', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(Form, self).__init__(children=children, **args)
