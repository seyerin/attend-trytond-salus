from trytond.wsgi import app
from trytond.pool import Pool


from werkzeug.wrappers import Response

from datetime import datetime


from flask import Flask, request, make_response, jsonify
from flask_cors import CORS
from datetime import datetime
import json
import numpy as np

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ini api untuk create inisialisasi wajah
@app.route('/face_recognition/create', methods=['POST'])
def create_face_record():

    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    data = request.json
    employee_id = data.get('employee_id')
    face_encoding = data.get('face_encoding')

    if not employee_id or not face_encoding:
        response = {'error': 'Missing employee_id or face_encoding'}
        resp = make_response(jsonify(response), 400)
    else:
        try:
            FaceRecognition = Pool().get('face.recognition')
            record = FaceRecognition.create_face_record_api(employee_id, face_encoding)
            response = {'success': True, 'record_id': record.id}
            resp = make_response(jsonify(response), 200)
        except ValueError as e:
            response = {'error': str(e)}
            resp = make_response(jsonify(response), 400)

    # Menambahkan CORS headers setelah membuat respon
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'POST'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'

    return resp

# ini face reocgnition untuk isi absensi
@app.route('/face_recognition/compare_and_record', methods=['POST'])
def compare_and_record():
    data = request.json
    employee_id = data.get('employee_id')
    face_encoding = np.array(json.loads(data.get('face_encoding')))
    check_type = data.get('check_type')  # "checkin" atau "checkout"

    if not employee_id or not face_encoding.any() or not check_type:
        return make_response(jsonify({'error': 'Missing employee_id, face_encoding, or check_type'}), 400)

    try:
        FaceRecognition = Pool().get('face.recognition')

        # Cari face encoding yang terkait dengan employee_id
        face_records = FaceRecognition.search([('employee', '=', employee_id)])
        if not face_records:
            return make_response(jsonify({'error': 'No face encoding found for this employee'}), 404)

        # Bandingkan encoding yang diterima dengan encoding di database
        for record in face_records:
            db_face_encoding = np.array(json.loads(record.face_encoding))
            # Hitung jarak antara encoding yang diterima dan yang ada di database
            distance = np.linalg.norm(db_face_encoding - face_encoding)

            if distance < 0.8:  
                AttendanceRecord = Pool().get('attendance.record')
                new_record = AttendanceRecord.create({
                    'employee': employee_id,
                    'check_time': datetime.now(),
                    'check_type': check_type,
                })
                return make_response(jsonify({'match': True, 'record_id': new_record.id}), 200)

        return make_response(jsonify({'match': False}), 200)

    except Exception as e:
        return make_response(jsonify({'error': str(e)}), 500)
    
@app.route('/geolocation/<int:company_id>', methods=['GET'])
def get_geolocation(company_id):
    CompanyGeo = Pool().get('company.geo')
    company_geo = CompanyGeo(company_id)
    return jsonify({
        'longitude': company_geo.longitude,
        'latitude': company_geo.latitude,
        'address': company_geo.address
    })

if __name__ == '__main__':
    app.run(debug=True)