from typing import Optional, TypeVar, Callable

T = TypeVar('T')

def convert_optional(input: T, converter: Callable[Optional[T], Optional[T]]) -> Optional[T]:
    if input:
        return input
    else:
        return None
 
