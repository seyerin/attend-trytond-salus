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
from trytond.rpc import RPC


from trytond.exceptions import UserError
import webbrowser
import urllib.parse

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


from werkzeug.utils import redirect

class FaceRecognition(ModelSQL, ModelView):
    'Face Recognition'
    __name__ = 'face.recognition'

    employee = fields.Many2One('company.employee', 'Employee', required=True,
        help="The employee associated with this face recognition record.")
    face_encoding = fields.Text('Face Encoding', required=True,
        help="The encoded face data for recognition. This could be a JSON or string of encoded features.")
    created_at = fields.DateTime('Created At', readonly=True,
        help="The date and time when this record was created.")
    
    face_reg_web = fields.Function(fields.Char('Initialize Face'),
        'on_change_with_face_reg')
    
    


    @classmethod
    def create_face_record_api(cls, employee_id, face_encoding):
        """
        Method to create a face recognition record.
        """
        Employee = Pool().get('company.employee')
        employee = Employee.browse(employee_id)
        if not employee:
            raise ValueError('Employee not found.')

        record = cls.create([{
            'employee': employee_id,
            'face_encoding': face_encoding,
            'created_at': fields.DateTime.now(),
        }])
        return record
    
    @classmethod
    def recognize_face(cls, records):
        #image_decoded = base64.b64decode(image_data.split(',')[1])
        np_array = np.frombuffer(image_decoded, np.uint8)
        img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

        # Load and encode the image
        face_encodings = face_recognition.face_encodings(img)
        if face_encodings:
            face_encoding = face_encodings[0]
            # Simpan face_encoding ke database atau lakukan validasi
            return "Face recognized and encoded."
        return "No face detected."

    # ini gak bisa
    @classmethod
    def initialize_face_encoding(cls, records):
        return {
            'type': 'ir.actions.act_url',
            'url': '/modules/face_recognition/static/html/camera.html',
            'target': 'new'
        }
    

    def action_open_webapp(self):
        # Check user permission (optional)
        user_id = self.context.get('user')
        if not user_id:
            raise UserError('User context is not available.')

        # Open the web application with parameters
        for record in self:
            url = (f"http://localhost:8080/face-recognition?"
                   f"employee_id={record.id}&"
                   f"face_id={record.face_recognition_id}")
            webbrowser.open(url)


    def action_initialize_face(self, *args):
        base_url = 'http://localhost:8080/face-camera'
        # Hanya mengirim employee_id
        #url = f"{base_url}?employee_id={self.employee.id}"
        
        # Membuka URL di browser default
        webbrowser.open(url)

    def on_change_with_face_reg(self, name=None):
        
        return 'http://localhost:8080/face-camera'