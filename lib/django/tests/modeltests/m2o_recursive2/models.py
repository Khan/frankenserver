"""
12. Relating a model to another model more than once

In this example, a ``Person`` can have a ``mother`` and ``father`` -- both of
which are other ``Person`` objects.

Set ``related_name`` to designate what the reverse relationship is called.
"""

from django.db import models

class Person(models.Model):
    full_name = models.CharField(maxlength=20)
    mother = models.ForeignKey('self', null=True, related_name='mothers_child_set')
    father = models.ForeignKey('self', null=True, related_name='fathers_child_set')

    def __str__(self):
        return self.full_name

__test__ = {'API_TESTS':"""
# Create two Person objects -- the mom and dad in our family.
>>> dad = Person(full_name='John Smith Senior', mother=None, father=None)
>>> dad.save()
>>> mom = Person(full_name='Jane Smith', mother=None, father=None)
>>> mom.save()

# Give mom and dad a kid.
>>> kid = Person(full_name='John Smith Junior', mother=mom, father=dad)
>>> kid.save()

>>> kid.mother
<Person: Jane Smith>
>>> kid.father
<Person: John Smith Senior>
>>> dad.fathers_child_set.all()
[<Person: John Smith Junior>]
>>> mom.mothers_child_set.all()
[<Person: John Smith Junior>]
>>> kid.mothers_child_set.all()
[]
>>> kid.fathers_child_set.all()
[]
"""}
