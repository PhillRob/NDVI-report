# !/usr/bin/python4
# -*- coding: UTF-8 -*-
# packages
import logging
import ee
from send_email import *
import sys
from definitions import *
import lib_ndvi 

def init_ee(email, credentials_file):
    credentials = ee.ServiceAccountCredentials(email, credentials_file)
    ee.Initialize(credentials)


# test settings

if __name__ == "__main__":
    local_test_run = False
    email_test_run = False
    
    if len(sys.argv) >= 2:
        # if test run is declared true through the command line we just run local tests
        local_test_run = int(sys.argv[1])
    if len(sys.argv) >= 3:
        email_test_run = int(sys.argv[2])
    
    
    if local_test_run:
        GEE_CREDENTIALS = '../../ee-phill-9248b486a4bc.json'
        LOGGING = 'ndvi-report-mailer.log'
    else:
        GEE_CREDENTIALS = '../credentials/gee_creds.json'
        LOGGING = 'mailer.log'
    
    service_account = 'mgaborlajos2@gmail.com'
    init_ee(service_account, GEE_CREDENTIALS)
    
    # logging
    logging.basicConfig(filename=LOGGING, level=logging.DEBUG)
    
    # this is where we'd list our projects - it can be moved to a json if desired
    projects = [
        {
            'GEOJSON_PATH': 'RUH01.geojson',
            'JSON_FILE_NAME': 'data01.json',
            'SCREENSHOT_SAVE_NAME': f'growth_decline_01.png',
            'REPORT_HTML': 'report.html',
            'LOGO': 'bpla-systems.png'
        },
        {
            'GEOJSON_PATH': 'RUH02.geojson',
            'JSON_FILE_NAME': 'data02.json',
            'SCREENSHOT_SAVE_NAME': f'growth_decline_02.png',
            'REPORT_HTML': 'report.html',
            'LOGO': 'bpla-systems.png'
        },
        {
            'GEOJSON_PATH': 'RUH03.geojson',
            'JSON_FILE_NAME': 'data03.json',
            'SCREENSHOT_SAVE_NAME': f'growth_decline_03.png',
            'REPORT_HTML': 'report.html',
            'LOGO': 'bpla-systems.png'
        }
    ]
    for i in projects:    
        lib_ndvi.Run(
            geojson_path=i['GEOJSON_PATH'], 
            json_file_name=i['JSON_FILE_NAME'], 
            screenshot_save_name_base=i['SCREENSHOT_SAVE_NAME'],
            credentials_path=i.get('CREDENTIALS_PATH'),
            report_html=i['REPORT_HTML'],
            logo=i['LOGO'],
            local_test_run=local_test_run,
            email_test_run=email_test_run
        )

# import AOI and set geometry
# TODO: chart changes changes over time
# TODO: interactive map in html email
