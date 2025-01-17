# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import attendance
from . import facerecognition
from . import geolocation
from . import api  

__all__ = ['register']


def register():
    Pool.register(
        geolocation.CompanyGeo,
        facerecognition.FaceRecognition,
        attendance.AbsensiRecord,
        attendance.Line,
        attendance.Period,
        attendance.SheetLine,
        attendance.Sheet,
        module='attendance', type_='model')
    Pool.register(
        attendance.Sheet_Timesheet,
        module='attendance', type_='model', depends=['timesheet'])
