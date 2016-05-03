#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
certs.py
~~~~~~~~

This module returns the preferred default CA certificate bundle.

If you are packaging Requests, e.g., for a Linux distribution or a managed
environment, you can change the definition of where() to return a separately
packaged CA bundle.
"""
import os.path

try:
    from certifi import where
except ImportError:
    # MOE:begin_strip
    try:
        from google3.pyglib import resources
    except ImportError:
        resources = None

    # MOE:end_strip
    def where():
        """Return the preferred certificate bundle."""
        # MOE:begin_strip
        try:
            if resources is not None:
            # Load from resources so that it works for .par files.
                return resources.GetResourceFilename(
                    'google3/third_party/py/requests/cacert.pem')
        except IOError:
            pass

        # vendored bundle inside Requests
        # MOE:end_strip
        return os.path.join(os.path.dirname(__file__), 'cacert.pem')

if __name__ == '__main__':
    print(where())
