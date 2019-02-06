import doctest
import unittest

def test_suite():
  suite = unittest.TestSuite()
  suite.addTest(doctest.DocTestSuite('pytz'))
  suite.addTest(doctest.DocTestSuite('pytz.tzinfo'))
  import test_tzinfo, test_lazy, test_docs
  suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(test_tzinfo))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(test_lazy))
  # test_docs doesn't test anything valuable. It just checks if README.txt is
  # ascii.
  # suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(test_docs))
  return suite
