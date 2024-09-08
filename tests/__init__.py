# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.attendance.tests.test_attendance import suite  # noqa: E501
except ImportError:
    from .test_attendance import suite

__all__ = ['suite']
