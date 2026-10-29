"""Compatibility layer providing Pydantic v2 classes or lightweight fallback.

Allows the codebase and test harness to run hermetically across environments
with full Pydantic v2 or minimal standard-library runtimes.
"""

try:
    from pydantic import BaseModel, Field, field_validator, HttpUrl  # type: ignore
except ImportError:
    # Standard library fallback shim for bare environments
    from typing import Any

    class BaseModel:
        """Lightweight standard library fallback for pydantic.BaseModel."""

        def __init__(self, **kwargs: Any):
            # Initialize defaults from annotations
            for ann_key in getattr(self.__class__, "__annotations__", {}):
                setattr(self, ann_key, None)

            # Populate class-level field defaults first
            for k, v in list(self.__class__.__dict__.items()):
                if not k.startswith("_") and not callable(v):
                    if hasattr(v, "_is_field_info"):
                        if v.default_factory:
                            setattr(self, k, v.default_factory())
                        elif v.default is not ...:
                            setattr(self, k, v.default)
                        else:
                            setattr(self, k, None)

            # Assign kwargs
            for k, v in kwargs.items():
                setattr(self, k, v)

            # Check min/max bounds if FieldInfo was defined
            for k, v in kwargs.items():
                field_info = getattr(self.__class__, k, None)
                if not getattr(field_info, "_is_field_info", False):
                    ann = getattr(self.__class__, "__annotations__", {}).get(k)
                    if ann and hasattr(ann, "__metadata__"):
                        for meta in ann.__metadata__:
                            if getattr(meta, "_is_field_info", False):
                                field_info = meta
                                break

                if getattr(field_info, "_is_field_info", False):
                    if field_info.ge is not None and v is not None and v < field_info.ge:
                        raise ValueError(f"Value for {k} must be >= {field_info.ge}, got {v}")
                    if field_info.le is not None and v is not None and v > field_info.le:
                        raise ValueError(f"Value for {k} must be <= {field_info.le}, got {v}")

            # Run any custom validators if defined
            for name, val in list(self.__class__.__dict__.items()):
                fn = val.__func__ if isinstance(val, classmethod) else val
                if getattr(fn, "_is_field_validator", False):
                    field_name = getattr(fn, "_field_name", "")
                    if hasattr(self, field_name):
                        curr_val = getattr(self, field_name)
                        new_val = fn(self.__class__, curr_val)
                        setattr(self, field_name, new_val)

        def model_dump(self) -> dict[str, Any]:
            result = {}
            for k, v in self.__dict__.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, BaseModel):
                    result[k] = v.model_dump()
                elif isinstance(v, list):
                    result[k] = [item.model_dump() if isinstance(item, BaseModel) else item for item in v]
                elif hasattr(v, "value"):
                    result[k] = v.value
                else:
                    result[k] = v
            return result

        def model_copy(self, *, update: dict[str, Any] | None = None) -> "BaseModel":
            dumped = self.model_dump()
            if update:
                dumped.update(update)
            return self.__class__(**dumped)

        def __repr__(self) -> str:
            attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_"))
            return f"{self.__class__.__name__}({attrs})"

        def __eq__(self, other: Any) -> bool:
            if not isinstance(other, self.__class__):
                return False
            return self.model_dump() == other.model_dump()

    class _FieldInfo:
        def __init__(self, default: Any = ..., default_factory: Any = None, ge: Any = None, le: Any = None):
            self._is_field_info = True
            self.default = default
            self.default_factory = default_factory
            self.ge = ge
            self.le = le

    def Field(default: Any = ..., default_factory: Any = None, ge: Any = None, le: Any = None, **kwargs: Any) -> Any:
        return _FieldInfo(default=default, default_factory=default_factory, ge=ge, le=le)

    def field_validator(field_name: str, **kwargs: Any):
        def decorator(fn):
            target = fn.__func__ if isinstance(fn, classmethod) else fn
            target._is_field_validator = True
            target._field_name = field_name
            fn._is_field_validator = True
            fn._field_name = field_name
            return fn

        return decorator

    HttpUrl = str

__all__ = ["BaseModel", "Field", "field_validator", "HttpUrl"]
