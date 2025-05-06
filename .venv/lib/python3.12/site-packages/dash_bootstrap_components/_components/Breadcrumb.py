# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Breadcrumb(Component):
    """A Breadcrumb component.
Use breadcrumbs to create a navigation breadcrumb in your app.

Keyword arguments:

- id (string; optional):
    The ID of the Breadcrumb.

- items (list of dicts; optional):
    The details of the items to render inside of this component.

    `items` is a list of dicts with keys:

    - label (string; optional):
        The label to display inside the breadcrumbs.

    - href (string; optional):
        URL of the resource to link to.

    - active (boolean; optional):
        If True, the item will be displayed as active.

    - external_link (boolean; optional):
        If True, clicking on the item will behave like a hyperlink. If
        False, the item will behave like a dcc.Link component, and can
        be used in conjunction with dcc.Location for navigation within
        a Dash app.

    - target (string; optional):
        Target attribute to pass on to the link. Only applies to
        external links.

    - title (string; optional):
        Title attribute for the inner anchor element.

- item_style (dict; optional):
    Additional inline CSS styles to apply to each item.

- class_name (string; optional):
    Additional CSS classes to apply to the Breadcrumb.

- item_class_name (string; optional):
    Additional CSS classes to apply to each item.

- key (string; optional):
    A unique identifier for the component, used to improve performance
    by React.js while rendering components  See
    https://react.dev/learn/rendering-lists#why-does-react-need-keys
    for more info.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Additional CSS classes
    to apply to the Breadcrumb.

- itemClassName (string; optional):
    **DEPRECATED** Use `item_class_name` instead.  Additional CSS
    classes to apply to each item.

- tag (dict; optional):
    HTML tag to use for the outer breadcrumb component. Default:
    \"nav\"."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Breadcrumb'
    Items = TypedDict(
        "Items",
            {
            "label": NotRequired[str],
            "href": NotRequired[str],
            "active": NotRequired[bool],
            "external_link": NotRequired[bool],
            "target": NotRequired[str],
            "title": NotRequired[str]
        }
    )

    _explicitize_dash_init = True

    def __init__(
        self,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        items: typing.Optional[typing.Sequence["Items"]] = None,
        style: typing.Optional[typing.Any] = None,
        item_style: typing.Optional[dict] = None,
        class_name: typing.Optional[str] = None,
        item_class_name: typing.Optional[str] = None,
        key: typing.Optional[str] = None,
        className: typing.Optional[str] = None,
        itemClassName: typing.Optional[str] = None,
        tag: typing.Optional[dict] = None,
        **kwargs
    ):
        self._prop_names = ['id', 'items', 'style', 'item_style', 'class_name', 'item_class_name', 'key', 'className', 'itemClassName', 'tag']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'items', 'style', 'item_style', 'class_name', 'item_class_name', 'key', 'className', 'itemClassName', 'tag']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        super(Breadcrumb, self).__init__(**args)
