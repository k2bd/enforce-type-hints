import typing
import unittest

import traits.api as traits_api

from typen._enforcer import Enforcer
from typen._typing import typing_to_trait
from typen.exceptions import ParameterTypeError
from typen.traits import ValidatedList


class TypingToTrait(unittest.TestCase):
    def test_typing_to_trait_list(self):
        typ = typing.List

        traits_typ = typing_to_trait(typ)

        self.assertIsInstance(traits_typ, traits_api.List)
        self.assertNotIsInstance(traits_typ, ValidatedList)

        traits_typ.validate(None, None, [1])
        traits_typ.validate(None, None, ["a"])
        with self.assertRaises(traits_api.TraitError):
            traits_typ.validate(None, None, "a")

    def test_typing_to_trait_list_of_int(self):
        typ = typing.List[int]

        traits_typ = typing_to_trait(typ)

        self.assertIsInstance(traits_typ, traits_api.List)
        self.assertIsInstance(traits_typ, ValidatedList)

        traits_typ.validate(None, None, [1])

        with self.assertRaises(traits_api.TraitError):
            traits_typ.validate(None, None, ["a"])

    def test_typing_to_trait_nested_list(self):
        typ = typing.List[typing.List[str]]

        traits_typ = typing_to_trait(typ)

        self.assertIsInstance(traits_typ, traits_api.List)
        self.assertIsInstance(traits_typ, ValidatedList)

        traits_typ.validate(None, None, [["a", "b"], ["c", "d"]])

        with self.assertRaises(traits_api.TraitError):
            traits_typ.validate(None, None, ["a"])

        with self.assertRaises(traits_api.TraitError):
            traits_typ.validate(None, None, [[1, "b"], ["c", "d"]])

    def test_typing_to_trait_int(self):
        typ = int

        traits_typ = typing_to_trait(typ)
        self.assertIs(traits_typ, int)

    def test_typing_to_trait_tuple(self):
        typ = typing.Tuple[int, str, int]

        traits_typ = typing_to_trait(typ)

        self.assertIsInstance(traits_typ, traits_api.Tuple)

        #self.fail("Complete test")


class EnforceTypingTypes(unittest.TestCase):
    def test_enforce_typing_list(self):
        def test_function(a: typing.List):
            pass
        e = Enforcer(test_function)

        e.verify_args([[1, 2]], {})
        e.verify_args([[1.1, 0.1]], {})
        e.verify_args([["a", "b"]], {})
        with self.assertRaises(ParameterTypeError):
            e.verify_args([1], {})
        with self.assertRaises(ParameterTypeError):
            e.verify_args([(1, 2)], {})

    def test_enforce_typing_list_spec(self):
        def test_function(a: typing.List[int]):
            pass
        e = Enforcer(test_function)

        e.verify_args([[1, 2]], {})
        with self.assertRaises(ParameterTypeError):
            e.verify_args([[1.1, 0.1]], {})
        with self.assertRaises(ParameterTypeError):
            e.verify_args([["a", "b"]], {})
        with self.assertRaises(ParameterTypeError):
            e.verify_args([1], {})
        with self.assertRaises(ParameterTypeError):
            e.verify_args([(1, 2)], {})

    def test_enforce_typing_tuple(self):
        def test_function(a: typing.Tuple):
            pass
        e = Enforcer(test_function)

        e.verify_args([(1, 2)], {})

        e.verify_args([[1.1, 0.1]], {})

        # Lists can be cast to tuple
        e.verify_args([["a", "b"]], {})

        with self.assertRaises(ParameterTypeError):
            e.verify_args([1], {})

    def test_enforce_typing_tuple_spec(self):
        def test_function(a: typing.Tuple[int, int]):
            pass
        e = Enforcer(test_function)

        e.verify_args([(1, 2)], {})

        with self.assertRaises(ParameterTypeError):
            e.verify_args([(1.1, 0.1)], {})

        with self.assertRaises(ParameterTypeError):
            e.verify_args([(1, "b")], {})

        with self.assertRaises(ParameterTypeError):
            e.verify_args([("a", "b")], {})

        with self.assertRaises(ParameterTypeError):
            e.verify_args((1,), {})

        with self.assertRaises(ParameterTypeError):
            e.verify_args([(1, 2, 3)], {})

        with self.assertRaises(ParameterTypeError):
            e.verify_args([[1, 2]], {})


#TODO: return types, args, kwargs
