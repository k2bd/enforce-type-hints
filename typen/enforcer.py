import inspect

from traits.api import Any, HasTraits, TraitError

from typen.exceptions import (
    ParameterTypeError,
    ReturnTypeError,
    UnspecifiedParameterTypeError,
    UnspecifiedReturnTypeError,
)


class Enforcer:
    def __init__(self, func, require_args=False, require_return=False):
        self.func = func
        spec = func.__annotations__
        params = inspect.signature(func).parameters
        unspecified = {key: Any for key in params.keys() if key not in spec}

        if unspecified and require_args:
            msg = "The following parameters must be given type hints: {!r}"
            raise UnspecifiedParameterTypeError(msg.format(list(unspecified.keys())))

        spec.update(unspecified)

        if "return" in spec.keys():
            self.returns = spec.pop("return")
        else:
            if require_return:
                msg = "A return type hint must be specified."
                raise UnspecifiedReturnTypeError(msg)
            self.returns = Any

        # Restore order of args
        self.args = [Arg(k, spec[k]) for k in params.keys()]

        # Validate defaults
        default_kwargs = {
            k: v.default for k, v in params.items()
            if v.default is not inspect.Parameter.empty
        }
        self.verify_args([], default_kwargs)

    def verify_args(self, passed_args, passed_kwargs):
        class FunctionSignature(HasTraits):
            pass

        fs = FunctionSignature()

        for arg in self.args:
            fs.add_trait(arg.name, arg.type)

        traits = {}
        for i, arg in enumerate(passed_args):
            expt_arg = self.args[i]
            traits[expt_arg.name] = arg
        traits.update(**passed_kwargs)

        try:
            fs.trait_set(**traits)
        except TraitError as err:
            name = err.name
            expt_type, = [arg.type for arg in self.args if arg.name == name]
            value = traits[name]
            msg = (
                "The {!r} parameter of {!r} must be {!r}, "
                "but a value of {!r} {!r} was specified."
            )
            raise ParameterTypeError(
                msg.format(name, self.func.__name__, expt_type, value, type(value))
            ) from None

    def verify_result(self, value):
        class ReturnType(HasTraits):
            pass

        rt = ReturnType()
        rt.add_trait("result", self.returns)

        try:
            rt.trait_set(result=value)
        except TraitError:
            msg = (
                "The return type of {!r} must be {!r}, "
                "but a value of {!r} {!r} was returned."
            )
            exception = ReturnTypeError(
                msg.format(self.func.__name__, self.returns, value, type(value)))
            exception.return_value = value
            raise exception from None


class Arg:
    def __init__(self, name, type):
        self.name = name
        self.type = type