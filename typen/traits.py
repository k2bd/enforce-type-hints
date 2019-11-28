from traits.api import List


class ValidatedList(List):
    """
    Defines a list that does validation on the internal type
    """

    def validate(self, object, name, value):
        value = super(ValidatedList, self).validate(object, name, value)

        for item in value:
            self.item_trait.validate(object, name, item)
