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
from flask import make_response, jsonify

import requests
import logging

from .exceptions import PeriodClosedError, PeriodTransitionError
import urllib.parse



class CompanyGeo(ModelSingleton, ModelSQL, ModelView):
    'Company Geo'
    __name__ = 'company.geo'
    

    company = fields.Many2One('company.company', "Company", required=True,
        help="The company the geolocation is associated with.")
    address = fields.Char('Address')
    longitude = fields.Function(fields.Float('Longitude', readonly =True),  'get_coordinates')
    latitude = fields.Function(fields.Float('Latitude', readonly =True), 'get_coordinates')
    max_distance = fields.Float('Max Distance (meters)', required=True,
        help="Maximum allowed distance in meters for face recognition.")
    # html_map = fields.Function(fields.Char('Map'), 'get_html_map')
    google_maps_url = fields.Function(fields.Char('Google Maps'),
        'on_change_with_google_maps_url')

    @fields.depends('address')
    def on_change_with_coordinates(self, name=None):
        if not self.address:
            self.longitude = None or 0.0
            self.latitude = None or 0.0
            return

        geolocator = Nominatim(user_agent="attendanceapp")
        try:
            location = geolocator.geocode(self.address)
            if location:
                self.longitude = location.longitude
                self.latitude = location.latitude
            else:
                self.longitude = None or 0.0
                self.latitude = None or 0.0
        except GeocoderTimedOut:
            print("Geocoding service timed out. Try again later.")
            self.longitude = None or 0.0
            self.latitude = None or 0.0
        except Exception as e:
            print(f"An error occurred: {e}")
            self.longitude = None or 0.0
            self.latitude = None or 0.0
        
        return self.longitude, self.latitude

    @classmethod
    def open_map(cls, records):
        # Ambil nama perusahaan dari record
        company_name = records[0].name
        # Encode nama perusahaan dan buat URL
        url = '/modules/attendance/static/html/map.html?name=' + urlencode({'name': company_name})
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new'
        }

    # def get_html_map(self, name):
    #     latitude = self.latitude or 0
    #     longitude = self.longitude or 0
    #     address = self.address or ''
    #     return '''
    #     <div id="map" style="height: 400px;"></div>
    #     <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
    #     <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
    #     <script>
    #         var map = L.map('map').setView([%f, %f], 13);
    #         L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    #             attribution: '&copy; OpenStreetMap contributors'
    #         }).addTo(map);
    #         var marker = L.marker([%f, %f]).addTo(map)
    #             .bindPopup('%s')
    #             .openPopup();
    #     </script>
    #     ''' % (latitude, longitude, latitude, longitude, address)



    @fields.depends('address')
    def on_change_with_google_maps_url(self, name=None):
        lang = Transaction().language[:2]
        url = ' '.join(self.address.splitlines())
        if url.strip():
            return 'http://maps.google.com/maps?hl=%s&q=%s' % (
                lang, urllib.parse.quote(url)
            )
        return ''
    
    @fields.depends('address')
    def get_coordinates(self, *args, **kwargs):
        print(f"Arguments received: args={args}, kwargs={kwargs}")
        if self.address:
            url = f"https://geocode.maps.co/search?q={self.address}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if data:
                    self.latitude = data[0].get('lat')
                    self.longitude = data[0].get('lon')
        return self.latitude, self.longitude