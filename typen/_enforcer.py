import inspect

from traits.api import HasTraits, TraitError

from typen._typing import typing_to_trait
from typen.exceptions import (
    ParameterTypeError,
    ReturnTypeError,
    UnspecifiedParameterTypeError,
    UnspecifiedReturnTypeError,
)

UNSPECIFIED = object()

#: List of methods exempt from strict return type annotation
RETURN_EXEMPT = ["__init__"]


class Enforcer:
    def __init__(
            self, func,
            require_args=False,
            require_return=False,
            ignore_self=False):
        self.func = func
        spec = func.__annotations__
        params = dict(inspect.signature(func).parameters)

        if ignore_self:
            require_return = require_return and func.__name__ not in RETURN_EXEMPT

        # Support for annotations on arg and kwarg packing
        self.packed_args_name = None
        self.packed_args_pos = None
        self.packed_args_spec = UNSPECIFIED
        self.packed_kwargs_name = None
        self.num_normal_keywords = None
        self.packed_kwargs_spec = UNSPECIFIED
        for i, (name, param) in enumerate(list(params.items())):
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                self.packed_args_name = name
                self.packed_args_pos = i
                if name in spec:
                    self.packed_args_spec = spec.pop(name)
                elif require_args:
                    msg = (
                        "Packed positional argument {!r} must be given a type "
                        "hint"
                    )
                    raise UnspecifiedParameterTypeError(msg.format(name))
                params.pop(name)
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                self.packed_kwargs_name = name
                if name in spec:
                    self.packed_kwargs_spec = spec.pop(name)
                elif require_args:
                    msg = (
                        "Packed keyword argument {!r} must be given a type "
                        "hint"
                    )
                    raise UnspecifiedParameterTypeError(msg.format(name))
                params.pop(name)
                self.num_normal_keywords = len(params)

        # If this is a method of some kind, ignore the first argument
        # (usually "self")
        self.ignored_self_name = None
        if ignore_self:
            self.ignored_self_name = list(params.keys())[0]

        if self.ignored_self_name is not None:
            params.pop(self.ignored_self_name)
            if self.ignored_self_name in spec:
                spec.pop(self.ignored_self_name)

        unspecified = {key: UNSPECIFIED for key in params.keys() if key not in spec}
        if unspecified and require_args:
            msg = "The following parameters of {!r} must be given type hints: {!r}"
            raise UnspecifiedParameterTypeError(
                msg.format(func.__name__, list(unspecified.keys()))
            )

        spec.update(unspecified)

        if "return" in spec.keys():
            self.returns = spec.pop("return")
        else:
            if require_return:
                msg = "A return type hint must be specified for {!r}."
                raise UnspecifiedReturnTypeError(msg.format(func.__name__))
            self.returns = UNSPECIFIED

        # Convert any non-trait type hints to traits
        spec = {
            k: to_traitable(v) for k, v in spec.items()
        }
        self.returns = to_traitable(self.returns)
        self.packed_args_spec = to_traitable(self.packed_args_spec)
        self.packed_kwargs_spec = to_traitable(self.packed_kwargs_spec)

        # Restore order of args
        self.args = [Arg(k, spec[k]) for k in params.keys()]

        # Store defaults for validation
        self.default_kwargs = {
            k: v.default for k, v in params.items()
            if v.default is not inspect.Parameter.empty
        }

        fs = FunctionSignature()
        rt = FunctionSignature()

        for arg in self.args:
            fs.add_trait(arg.name, arg.type)
            arg.validator = fs.trait(arg.name)

        if self.packed_args_spec is not UNSPECIFIED:
            fs.add_trait(self.packed_args_name, self.packed_args_spec)
            self.packed_args_validator = fs.trait(self.packed_args_name)

        if self.packed_kwargs_spec is not UNSPECIFIED:
            fs.add_trait(self.packed_kwargs_name, self.packed_kwargs_spec)
            self.packed_kwargs_validator = fs.trait(self.packed_kwargs_name)

        rt.add_trait("result", self.returns)
        self.result_validator = rt.trait("result")

    def verify_args(self, passed_args, passed_kwargs):
        if self.ignored_self_name is not None:
            # Handle the rare case that self is passed as a kwarg
            if self.ignored_self_name in passed_kwargs:
                passed_kwargs = {
                    k: v for k, v in passed_kwargs.items()
                    if k != self.ignored_self_name
                }
            else:
                passed_args = passed_args[1:]

        packed_args = []
        packed_kwargs = {}
        if self.packed_args_name is not None:
            packed_args = passed_args[self.packed_args_pos:]
            passed_args = passed_args[:self.packed_args_pos]
        if self.packed_kwargs_name is not None:
            packed_kwargs = {
                key: passed_kwargs[key] for key in
                list(passed_kwargs.keys())[self.num_normal_keywords-1:]
            }
            passed_kwargs = {
                key: passed_kwargs[key] for key in
                list(passed_kwargs.keys())[:self.num_normal_keywords-1]
            }

        for i, arg in enumerate(self.args):
            if arg.type is UNSPECIFIED:
                continue

            if i < len(passed_args):
                value = passed_args[i]
            elif arg.name in passed_kwargs:
                value = passed_kwargs[arg.name]
            elif arg.name in self.default_kwargs:
                value = self.default_kwargs[arg.name]
            else:
                continue

            try:
                arg.validator.validate(None, None, value)
            except TraitError:
                msg = (
                    "The {!r} parameter of {!r} must be {!r}, "
                    "but a value of {!r} {!r} was specified."
                )
                raise ParameterTypeError(
                    msg.format(
                        arg.name, self.func.__name__, arg.type, value, type(value))
                ) from None

        if self.packed_args_spec is not UNSPECIFIED:
            for value in packed_args:
                try:
                    self.packed_args_validator.validate(None, None, value)
                except TraitError:
                    msg = (
                        "The {!r} parameters of {!r} must be {!r}, "
                        "but a value of {!r} {!r} was specified."
                    )
                    raise ParameterTypeError(
                        msg.format(
                            self.packed_args_name,
                            self.func.__name__,
                            self.packed_args_spec,
                            value,
                            type(value)
                        )
                    ) from None
        if self.packed_kwargs_spec is not UNSPECIFIED:
            for key, value in packed_kwargs.items():
                try:
                    self.packed_kwargs_validator.validate(None, None, value)
                except TraitError:
                    msg = (
                        "The {!r} keywords of {!r} must have values of type "
                        "{!r}, but {!r}:{!r} {!r} was specified."
                    )
                    raise ParameterTypeError(
                        msg.format(
                            self.packed_kwargs_name,
                            self.func.__name__,
                            self.packed_kwargs_spec,
                            key,
                            value,
                            type(value),
                        )
                    ) from None

    def verify_result(self, value):
        if self.returns is UNSPECIFIED:
            return

        try:
            self.result_validator.validate(None, None, value)
        except TraitError:
            msg = (
                "The return type of {!r} must be {!r}, "
                "but a value of {!r} {!r} was returned."
            )
            exception = ReturnTypeError(
                msg.format(self.func.__name__, self.returns, value, type(value)))
            exception.return_value = value
            raise exception from None


def to_traitable(param_type):
    """
    Function to attempt to turn the input parameter type to a suitable Traits
    type.
    """
    param_type = typing_to_trait(param_type)
    # More conversion attempts can be made if more than just typing types
    # are supported

    return param_type


class FunctionSignature(HasTraits):
    pass


class Arg:
    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.validator = None
