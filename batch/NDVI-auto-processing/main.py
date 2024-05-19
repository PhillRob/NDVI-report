# !/usr/bin/python3
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
def main():
    # set those to True and it will use local vars below *
    local_test_run = False
    email_test_run = False
    
    if len(sys.argv) >= 2:
        # if test run is declared true through the command line we just run local tests
        local_test_run = int(sys.argv[1])
    if len(sys.argv) >= 3:
        email_test_run = int(sys.argv[2])
    
    # here are the local vars
    if local_test_run:
        GEE_CREDENTIALS = '../../ee-phill-9248b486a4bc.json'
        LOGGING = '../../ndvi-report-mailer.log'
    else:
        GEE_CREDENTIALS = '../ee-phill-9248b486a4bc.json'
        LOGGING = 'mailer.log'

    # change to personal account
    service_account = 'ndvi-mailer@ee-phill.iam.gserviceaccount.com'
    init_ee(service_account, GEE_CREDENTIALS)
    
    # logging
    logging.basicConfig(filename=LOGGING, level=logging.DEBUG)
    
    # this is where we list our projects. You need update those path vars to match the local files.
    projects = [
        {
            'GEOJSON_PATH': 'trial3.geojson',
            'JSON_FILE_NAME': 'data03.json',
            'SCREENSHOT_SAVE_NAME': f'growth_decline',
            'REPORT_HTML': 'report.html',
            'LOGO': 'bpla-systems.png',
            'CREDENTIALS_PATH': 'credentials/credentials.json',
            'OUTPUT_FOLDER': 'output'
        }
    ]
    for i in projects:
        lib_ndvi.Run(
            geojson_path=i['GEOJSON_PATH'], 
            screenshot_save_name_base=i['SCREENSHOT_SAVE_NAME'],
            credentials_path=i.get('CREDENTIALS_PATH'),
            report_html=i['REPORT_HTML'],
            output_folder=i['OUTPUT_FOLDER'],
            logo=i['LOGO'],
            local_test_run=local_test_run,
            email_test_run=email_test_run
        )

if __name__ == "__main__":
    main()
