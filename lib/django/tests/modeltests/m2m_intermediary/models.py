"""
9. Many-to-many relationships via an intermediary table

For many-to-many relationships that need extra fields on the intermediary
table, use an intermediary model.

In this example, an ``Article`` can have multiple ``Reporter``s, and each
``Article``-``Reporter`` combination (a ``Writer``) has a ``position`` field,
which specifies the ``Reporter``'s position for the given article (e.g. "Staff
writer").
"""

from django.db import models

class Reporter(models.Model):
    first_name = models.CharField(maxlength=30)
    last_name = models.CharField(maxlength=30)

    def __str__(self):
        return "%s %s" % (self.first_name, self.last_name)

class Article(models.Model):
    headline = models.CharField(maxlength=100)
    pub_date = models.DateField()

    def __str__(self):
        return self.headline

class Writer(models.Model):
    reporter = models.ForeignKey(Reporter)
    article = models.ForeignKey(Article)
    position = models.CharField(maxlength=100)

    def __str__(self):
        return '%s (%s)' % (self.reporter, self.position)

__test__ = {'API_TESTS':"""
# Create a few Reporters.
>>> r1 = Reporter(first_name='John', last_name='Smith')
>>> r1.save()
>>> r2 = Reporter(first_name='Jane', last_name='Doe')
>>> r2.save()

# Create an Article.
>>> from datetime import datetime
>>> a = Article(headline='This is a test', pub_date=datetime(2005, 7, 27))
>>> a.save()

# Create a few Writers.
>>> w1 = Writer(reporter=r1, article=a, position='Main writer')
>>> w1.save()
>>> w2 = Writer(reporter=r2, article=a, position='Contributor')
>>> w2.save()

# Play around with the API.
>>> a.writer_set.select_related().order_by('-position')
[<Writer: John Smith (Main writer)>, <Writer: Jane Doe (Contributor)>]
>>> w1.reporter
<Reporter: John Smith>
>>> w2.reporter
<Reporter: Jane Doe>
>>> w1.article
<Article: This is a test>
>>> w2.article
<Article: This is a test>
>>> r1.writer_set.all()
[<Writer: John Smith (Main writer)>]
"""}
