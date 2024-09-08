# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import datetime as dt
from collections import defaultdict
from itertools import chain

try:
    import pytz
except ImportError:
    pytz = None

from sql import Window, Literal, Null, Column
from sql.aggregate import Min, Sum
from sql.conditionals import Coalesce
from sql.functions import NthValue, CurrentTimestamp, Function

from trytond import backend
from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import Workflow, ModelView, ModelSQL, ModelSingleton, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


from werkzeug.utils import redirect


from .exceptions import PeriodClosedError, PeriodTransitionError


class SQLiteStrftime(Function):
    __slots__ = ()
    _function = 'STRFTIME'
    'Company Geo'
    __name__ = 'company.geo'

    company = fields.Many2One('company.company', "Company", required=True,
        help="The company the geolocation is associated with.")
    address = fields.Char('Address')
    longitude = fields.Float('Longitude', readonly =True )
    latitude = fields.Float('Latitude', readonly =True)
    html_map = fields.Function(fields.Char('Map'), 'get_html_map')

    @fields.depends('address')
    def on_change_with_coordinates(self):
        if not self.address:
            self.longitude = None
            self.latitude = None
            return

        geolocator = Nominatim(user_agent="company_geo_app")
        try:
            location = geolocator.geocode(self.address)
            if location:
                self.longitude = location.longitude
                self.latitude = location.latitude
            else:
                self.longitude = None
                self.latitude = None
        except GeocoderTimedOut:
            print("Geocoding service timed out. Try again later.")
            self.longitude = None
            self.latitude = None
        except Exception as e:
            print(f"An error occurred: {e}")
            self.longitude = None
            self.latitude = None
   

    def get_html_map(self, name):
        return '''
        <div id="map" style="height: 400px;"></div>
        <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
        <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
        <script>
            var map = L.map('map').setView([%(latitude)s, %(longitude)s], 13);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(map);
            var marker = L.marker([%(latitude)s, %(longitude)s]).addTo(map)
                .bindPopup('%(address)s')
                .openPopup();
        </script>
        ''' % {'latitude': self.latitude or 0, 'longitude': self.longitude or 0, 'address': self.address or ''}


class AbsensiRecord(ModelSQL, ModelView):
    'Absensi Record'
    __name__ = 'absensi.record'
    
    employee = fields.Many2One('company.employee', 'Employee', required=True)
    check_in = fields.DateTime('Check-in Time')
    check_out = fields.DateTime('Check-out Time')
    location = fields.Char('Location')

    check_action = fields.Selection([
        ('check_in', 'Check-In'),
        ('check_out', 'Check-Out'),
    ], 'Action', required=True)

    @staticmethod
    def __setup__():
        super(AbsensiRecord, AbsensiRecord).__setup__()

class AttendanceFaceRecognition(ModelView):
    'Attendance Face Recognition'
    __name__ = 'attendance.face.recognition'

    @classmethod
    def initialize_face_encoding(cls, employee_id):
        # Initialize the camera
        video_capture = cv2.VideoCapture(0)

        print("Please look at the camera to capture your face.")

        # Capture a single frame
        ret, frame = video_capture.read()
        video_capture.release()
        cv2.destroyAllWindows()

        if not ret:
            print("Failed to capture image.")
            return

        # Process the captured image
        rgb_frame = frame[:, :, ::-1]
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        if not face_encodings:
            print("No faces found in the image.")
            return

        # Assuming only one face is detected
        face_encoding = face_encodings[0]

        # Save the face encoding to the database
        employee = Employee.get(employee_id)
        if employee:
            FaceRecognition.create({
                'employee': employee_id,
                'face_encoding': face_recognition.face_encodings_to_string(face_encoding),
                'created_at': datetime.datetime.now()
            })
            print(f"Face encoding for employee {employee.rec_name} saved successfully.")
        else:
            print("Employee cannot safe the encoding.")

    @classmethod
    def recognize_face(cls, records):
        face_encodings, known_face_names = FaceRecognition.get_face_encodings()

        # Initialize the camera
        video_capture = cv2.VideoCapture(0)
        process_this_frame = True

        while True:
            ret, frame = video_capture.read()
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = small_frame[:, :, ::-1]

            if process_this_frame:
                face_locations = face_recognition.face_locations(rgb_small_frame)
                current_face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                for face_encoding in current_face_encodings:
                    matches = face_recognition.compare_faces(face_encodings, face_encoding)

                    if True in matches:
                        first_match_index = matches.index(True)
                        name = known_face_names[first_match_index]
                        print(f"Recognized: {name}")
                        break

            process_this_frame = not process_this_frame

        video_capture.release()
        cv2.destroyAllWindows()
































class Line(ModelSQL, ModelView):
    "Attendance Line"
    __name__ = 'attendance.line'

    # ini satu company punya banyak attendance
    company = fields.Many2One('company.company', "Company", required=True,
        help="The company which the employee attended.")
    employee = fields.Many2One('company.employee', "Employee", required=True,
        domain=[
            ('company', '=', Eval('company')),
            ['OR',
                ('start_date', '=', None),
                ('start_date', '<=', Eval('date')),
                ],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', Eval('date')),
                ],
            ],
        depends=['company', 'date'])
    at = fields.DateTime("At", required=True)
    date = fields.Date("Date", required=True)
    type = fields.Selection([
            ('in', 'In'),
            ('out', 'Out'),
            ], "Type", required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('at', 'DESC'))
        # Do not cache default_at
        cls.__rpc__['default_get'].cache = None

    @classmethod
    def default_at(cls):
        return dt.datetime.now()

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_employee(cls):
        return Transaction().context.get('employee')

    @fields.depends('at', 'company')
    def on_change_with_date(self):
        if not self.at:
            return
        at = self.at
        if pytz and self.company and self.company.timezone:
            timezone = pytz.timezone(self.company.timezone)
            at = pytz.utc.localize(self.at, is_dst=None).astimezone(timezone)
        return at.date()

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        return '%s@%s' % (self.employee.rec_name, lang.strftime(self.at))

    @classmethod
    def create(cls, vlist):
        lines = super().create(vlist)
        to_write = defaultdict(list)
        for line in lines:
            date = line.on_change_with_date()
            if line.date != date:
                to_write[date].append(line)
        if to_write:
            cls.write(*chain([l, {'date': d}] for d, l in to_write.items()))
        return lines

    @classmethod
    def write(cls, *args):
        super().write(*args)

        to_write = defaultdict(list)
        actions = iter(args)
        for lines, values in zip(actions, actions):
            for line in lines:
                date = line.on_change_with_date()
                if line.date != date:
                    to_write[date].append(line)
        if to_write:
            cls.write(*chain([l, {'date': d}] for d, l in to_write.items()))

    @classmethod
    def delete(cls, records):
        cls.check_closed_period(records, msg='delete')
        super().delete(records)

    @classmethod
    def validate(cls, records):
        super().validate(records)
        cls.check_closed_period(records)

    @classmethod
    def check_closed_period(cls, records, msg='modify'):
        pool = Pool()
        Period = pool.get('attendance.period')
        for record in records:
            period_date = Period.get_last_period_date(record.company)
            if period_date and period_date > record.at:
                raise PeriodClosedError(
                    gettext('attendance.msg_%s_period_close' % msg,
                        attendance=record.rec_name,
                        period=period_date))

    @fields.depends('employee', 'at', 'id')
    def on_change_with_type(self):
        records = self.search([
                ('employee', '=', self.employee),
                ('at', '<', self.at),
                ('id', '!=', self.id),
                ],
            order=[('at', 'desc')],
            limit=1)
        if records:
            record, = records
            return {'in': 'out', 'out': 'in'}.get(record.type)
        else:
            return 'in'


class Period(Workflow, ModelSQL, ModelView):
    "Attendance Period"
    __name__ = 'attendance.period'
    _states = {
        'readonly': Eval('state') == 'closed',
        }
    _depends = ['state']

    _last_period_cache = Cache('attendance.period', context=False)

    ends_at = fields.DateTime("Ends at", required=True, states=_states,
        depends=_depends)
    company = fields.Many2One('company.company', "Company", required=True,
        states=_states, depends=_depends,
        help="The company the period is associated with.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('closed', 'Closed'),
        ], 'State', select=True, readonly=True,
        help="The current state of the attendance period.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= set((
                ('draft', 'closed'),
                ('closed', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    'depends': ['state'],
                    },
                'close': {
                    'invisible': Eval('state') == 'closed',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'draft'

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        return lang.strftime(self.ends_at)

    @classmethod
    def get_last_period_date(cls, company):
        key = int(company)
        result = cls._last_period_cache.get(key, -1)
        if result == -1:
            records = cls.search([
                    ('company', '=', company),
                    ('state', '=', 'closed'),
                    ],
                order=[('ends_at', 'DESC')],
                limit=1)
            if records:
                record, = records
                result = record.ends_at
            else:
                result = None
            cls._last_period_cache.set(key, result)
        return result

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, periods):
        for period in periods:
            records = cls.search([
                    ('company', '=', period.company),
                    ('state', '=', 'closed'),
                    ('ends_at', '>', period.ends_at),
                    ],
                order=[('ends_at', 'ASC')],
                limit=1)
            if records:
                record, = records
                raise PeriodTransitionError(
                    gettext('attendance.msg_draft_period_previous_closed',
                        period=period.rec_name,
                        other_period=record.rec_name))
        cls._last_period_cache.clear()

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, periods):
        for period in periods:
            records = cls.search([
                    ('company', '=', period.company),
                    ('state', '=', 'draft'),
                    ('ends_at', '<', period.ends_at),
                    ],
                order=[('ends_at', 'ASC')],
                limit=1)
            if records:
                record, = records
                raise PeriodTransitionError(
                    gettext('attendance.msg_close_period_previous_open',
                        period=period.rec_name,
                        other_period=record.rec_name))
        cls._last_period_cache.clear()


class SheetLine(ModelSQL, ModelView):
    "Attendance SheetLine"
    __name__ = 'attendance.sheet.line'

    company = fields.Many2One('company.company', "Company")
    employee = fields.Many2One('company.employee', "Employee")
    from_ = fields.DateTime("From")
    to = fields.DateTime("To")
    duration = fields.TimeDelta("Duration")
    date = fields.Date("Date")
    sheet = fields.Many2One('attendance.sheet', "Sheet")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('from_', 'DESC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Attendance = pool.get('attendance.line')

        transaction = Transaction()
        database = transaction.database

        attendance = Attendance.__table__()

        if database.has_window_functions():
            window = Window(
                [attendance.employee],
                order_by=[attendance.at.asc],
                frame='ROWS', start=0, end=1)
            type = NthValue(attendance.type, 1, window=window)
            from_ = NthValue(attendance.at, 1, window=window)
            to = NthValue(attendance.at, 2, window=window)
            date = NthValue(attendance.date, 1, window=window)
            query = attendance.select(
                attendance.id.as_('id'),
                attendance.company.as_('company'),
                attendance.employee.as_('employee'),
                type.as_('type'),
                from_.as_('from_'),
                to.as_('to'),
                date.as_('date'))

            sheet = (
                Min(query.id * 2, window=Window([query.employee, query.date])))
        else:
            next_attendance = Attendance.__table__()
            to = next_attendance.select(
                next_attendance.at,
                where=(next_attendance.employee == attendance.employee)
                & (next_attendance.at > attendance.at),
                order_by=[next_attendance.at.asc],
                limit=1)
            query = attendance.select(
                attendance.id.as_('id'),
                attendance.company.as_('company'),
                attendance.employee.as_('employee'),
                attendance.type.as_('type'),
                attendance.at.as_('from_'),
                to.as_('to'),
                attendance.date.as_('date'))

            query2 = copy.copy(query)
            sheet = query2.select(
                Min(query2.id * 2),
                where=(query2.employee == query.employee)
                & (query2.date == query.date))

        from_ = Column(query, 'from_')
        if backend.name == 'sqlite':
            # As SQLite does not support operation on datetime
            # we convert datetime into seconds
            duration = (
                SQLiteStrftime('%s', query.to) - SQLiteStrftime('%s', from_))
        else:
            duration = query.to - from_
        return query.select(
            query.id.as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
            query.company.as_('company'),
            query.employee.as_('employee'),
            from_.as_('from_'),
            query.to.as_('to'),
            query.date.as_('date'),
            duration.as_('duration'),
            sheet.as_('sheet'),
            where=query.type == 'in')


class Sheet(ModelSQL, ModelView):
    "Attendance Sheet"
    __name__ = 'attendance.sheet'

    company = fields.Many2One('company.company', "Company")
    employee = fields.Many2One('company.employee', "Employee")
    duration = fields.TimeDelta("Duration")
    date = fields.Date("Date")
    lines = fields.One2Many('attendance.sheet.line', 'sheet', "Lines")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Line = pool.get('attendance.sheet.line')

        line = Line.__table__()

        return line.select(
            (Min(line.id * 2)).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
            line.company.as_('company'),
            line.employee.as_('employee'),
            Sum(line.duration).as_('duration'),
            line.date.as_('date'),
            group_by=[line.company, line.employee, line.date])


class Sheet_Timesheet(metaclass=PoolMeta):
    __name__ = 'attendance.sheet'

    timesheet_duration = fields.TimeDelta("Timesheet Duration")

    @classmethod
    def table_query(cls):
        pool = Pool()
        Timesheet = pool.get('timesheet.line')
        line = Timesheet.__table__()
        timesheet = line.select(
            Min(line.id * 2 + 1).as_('id'),
            line.company.as_('company'),
            line.employee.as_('employee'),
            Sum(line.duration).as_('duration'),
            line.date.as_('date'),
            group_by=[line.company, line.employee, line.date])
        attendance = super().table_query()
        return (attendance
            .join(
                timesheet, 'FULL' if backend.name != 'sqlite' else 'LEFT',
                condition=(attendance.company == timesheet.company)
                & (attendance.employee == timesheet.employee)
                & (attendance.date == timesheet.date))
            .select(
                Coalesce(attendance.id, timesheet.id).as_('id'),
                Literal(0).as_('create_uid'),
                CurrentTimestamp().as_('create_date'),
                cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
                cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
                Coalesce(attendance.company, timesheet.company).as_('company'),
                Coalesce(
                    attendance.employee, timesheet.employee).as_('employee'),
                attendance.duration.as_('duration'),
                timesheet.duration.as_('timesheet_duration'),
                Coalesce(attendance.date, timesheet.date).as_('date'),
                ))
