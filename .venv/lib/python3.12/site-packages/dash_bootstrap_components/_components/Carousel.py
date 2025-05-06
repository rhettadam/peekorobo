# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class Carousel(Component):
    """A Carousel component.
Carousel. for creating Bootstrap carousel.  This component is a slideshow
for cycling through a series of content.

Keyword arguments:

- id (string; optional):
    The ID of the Carousel.

- items (list of dicts; required):
    The items to display on the slides in the Carousel.

    `items` is a list of dicts with keys:

    - src (string; optional):
        The URL of the image.

    - alt (string; optional):
        The alternate text for an image, if the image cannot be
        displayed.

    - header (string; optional):
        The header of the text on the slide. It is displayed in a <h5>
        element.

    - caption (string; optional):
        A caption for the item.

    - img_style (dict; optional):
        Additional inline CSS styles for the image.

    - img_class_name (string; optional):
        The className for the image.  The default is 'd-block w-100'.

    - caption_class_name (string; optional):
        The class name for the header and caption container.

    - href (string; optional):
        Optional hyperlink to add to the item. Item will be rendered
        as a HTML <a> or as a Dash-style link depending on whether the
        link is deemed to be internal or external. Override this
        automatic detection with the external_link argument.

    - target (string; optional):
        Optional target attribute for the link. Only applies if `href`
        is set, default `_self`.

    - external_link (boolean; optional):
        If True, clicking on the item will behave like a hyperlink. If
        False, the item will behave like a dcc.Link component, and can
        be used in conjunction with dcc.Location for navigation within
        a Dash app.

    - key (string; optional):
        A unique identifier for the slide, used to improve performance
        by React.js while rendering components.  See
        https://react.dev/learn/rendering-lists#why-does-react-need-keys
        for more info.

    - imgClassName (string; optional):
        **DEPRECATED** Use `img_class_name` instead.  The className
        for the image. The default is 'd-block w-100'.

    - captionClassName (string; optional):
        **DEPRECATED** Use `caption_class_name` instead.  The class
        name for the header and caption container.

- active_index (number; default 0):
    The current visible slide number.

- interval (number; optional):
    The interval at which the Carousel automatically cycles through
    the slides. If None, the Carousel will not automatically cycle.

- controls (boolean; default True):
    Show the Carousel previous and next arrows for changing the
    current slide.

- indicators (boolean; default True):
    Show a set of slide position indicators.

- class_name (string; optional):
    Defines the className of the carousel container. Additional CSS
    classes to apply to the Carousel.

- slide (boolean; optional):
    Enables animation on the Carousel as it transitions between
    slides.

- variant (a value equal to: 'dark'; optional):
    Add `variant=\"dark\"` to the Carousel for darker controls,
    indicators, and captions.

- persistence (boolean | string | number; optional):
    Used to allow user interactions to be persisted when the page is
    refreshed. See https://dash.plotly.com/persistence for more
    details.

- persisted_props (list of a value equal to: 'active_index's; optional):
    Properties whose user interactions will persist after refreshing
    the component or the page. Since only `value` is allowed this prop
    can normally be ignored.

- persistence_type (a value equal to: 'local', 'session', 'memory'; optional):
    Where persisted user changes will be stored: - memory: only kept
    in memory, reset on page refresh. - local: window.localStorage,
    data is kept after the browser quit. - session:
    window.sessionStorage, data is cleared once the browser quit.

- className (string; optional):
    **DEPRECATED** Use `class_name` instead.  Defines the className of
    the carousel container. Additional CSS classes to apply to the
    Carousel."""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'dash_bootstrap_components'
    _type = 'Carousel'
    Items = TypedDict(
        "Items",
            {
            "src": NotRequired[str],
            "alt": NotRequired[str],
            "header": NotRequired[str],
            "caption": NotRequired[str],
            "img_style": NotRequired[dict],
            "img_class_name": NotRequired[str],
            "caption_class_name": NotRequired[str],
            "href": NotRequired[str],
            "target": NotRequired[str],
            "external_link": NotRequired[bool],
            "key": NotRequired[str],
            "imgClassName": NotRequired[str],
            "captionClassName": NotRequired[str]
        }
    )

    _explicitize_dash_init = True

    def __init__(
        self,
        id: typing.Optional[typing.Union[str, dict]] = None,
        *,
        items: typing.Optional[typing.Sequence["Items"]] = None,
        active_index: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        interval: typing.Optional[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]] = None,
        controls: typing.Optional[bool] = None,
        indicators: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        class_name: typing.Optional[str] = None,
        slide: typing.Optional[bool] = None,
        variant: typing.Optional[Literal["dark"]] = None,
        persistence: typing.Optional[typing.Union[bool, str, typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex]]] = None,
        persisted_props: typing.Optional[typing.Sequence[Literal["active_index"]]] = None,
        persistence_type: typing.Optional[Literal["local", "session", "memory"]] = None,
        className: typing.Optional[str] = None,
        **kwargs
    ):
        self._prop_names = ['id', 'items', 'active_index', 'interval', 'controls', 'indicators', 'style', 'class_name', 'slide', 'variant', 'persistence', 'persisted_props', 'persistence_type', 'className']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'items', 'active_index', 'interval', 'controls', 'indicators', 'style', 'class_name', 'slide', 'variant', 'persistence', 'persisted_props', 'persistence_type', 'className']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ['items']:
            if k not in args:
                raise TypeError(
                    'Required argument `' + k + '` was not specified.')

        super(Carousel, self).__init__(**args)
