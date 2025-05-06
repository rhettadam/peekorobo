# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Pagination(Component):
    """A Pagination component.
The container for presentational components for building a pagination UI.
Individual pages should be added as children using the `PaginationItem`
component.

Keyword arguments:

- id (string; optional):
    The ID of the Pagination.

- active_page (number; default 1):
    The currently active page.

- min_value (number; default 1):
    Minimum (leftmost) value to appear in the pagination.

- max_value (number; required):
    Maximum (rightmost) value to appear in the pagination. Must be
    defined. If the `min_value` and `step` together cannot reach this
    value, then the next stepped value is used as the maximum.

- step (number; default 1):
    Page increment step.

- size (a value equal to: 'sm', 'lg'; optional):
    Set the size of all page items in the Pagination.

- fully_expanded (boolean; default True):
    When True, this will display all numbers between `min_value` and
    `max_value`.

- previous_next (boolean; default False):
    When True, this will display a previous and next icon before and
    after the individual page numbers.

- first_last (boolean; default False):
    When True, this will display a first and last icon at the
    beginning and end of the Pagination.

- class_name (string; optional):
    Additional CSS classes to apply to the Pagination.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Pagination."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Pagination'

    _explicitize_dash_init = True

    def __init__(
        self,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        active_page: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        min_value: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        max_value: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        step: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        size: typing.Optional[Literal["sm", "lg"]] = None,
        fully_expanded: typing.Optional[bool] = None,
        previous_next: typing.Optional[bool] = None,
        first_last: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['id', 'active_page', 'min_value', 'max_value', 'step', 'size', 'fully_expanded', 'previous_next', 'first_last', 'style', 'class_name', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'active_page', 'min_value', 'max_value', 'step', 'size', 'fully_expanded', 'previous_next', 'first_last', 'style', 'class_name', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ['max_value']:
            if k not in args:
                raise TypeError(
                    'Required argument `' + k + '` was not specified.')

        super(Pagination, self).__init__(**args)
