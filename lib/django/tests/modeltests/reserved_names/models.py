"""
18. Using SQL reserved names

Need to use a reserved SQL name as a column name or table name? Need to include
a hyphen in a column or table name? No problem. Django quotes names
appropriately behind the scenes, so your database won't complain about
reserved-name usage.
"""

from django.db import models

class Thing(models.Model):
    when = models.CharField(maxlength=1, primary_key=True)
    join = models.CharField(maxlength=1)
    like = models.CharField(maxlength=1)
    drop = models.CharField(maxlength=1)
    alter = models.CharField(maxlength=1)
    having = models.CharField(maxlength=1)
    where = models.DateField(maxlength=1)
    has_hyphen = models.CharField(maxlength=1, db_column='has-hyphen')
    class Meta:
       db_table = 'select'

    def __str__(self):
        return self.when

__test__ = {'API_TESTS':"""
>>> import datetime
>>> day1 = datetime.date(2005, 1, 1)
>>> day2 = datetime.date(2006, 2, 2)
>>> t = Thing(when='a', join='b', like='c', drop='d', alter='e', having='f', where=day1, has_hyphen='h')
>>> t.save()
>>> print t.when
a

>>> u = Thing(when='h', join='i', like='j', drop='k', alter='l', having='m', where=day2)
>>> u.save()
>>> print u.when
h

>>> Thing.objects.order_by('when')
[<Thing: a>, <Thing: h>]
>>> v = Thing.objects.get(pk='a')
>>> print v.join
b
>>> print v.where
2005-01-01
>>> Thing.objects.order_by('select.when')
[<Thing: a>, <Thing: h>]

>>> Thing.objects.dates('where', 'year')
[datetime.datetime(2005, 1, 1, 0, 0), datetime.datetime(2006, 1, 1, 0, 0)]

>>> Thing.objects.filter(where__month=1)
[<Thing: a>]
"""}
