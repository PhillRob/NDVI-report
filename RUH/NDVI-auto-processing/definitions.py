
# !/usr/bin/python4
# -*- coding: UTF-8 -*-
# packages
import ee
import folium
from datetime import datetime, timedelta, timezone


def get_processing_time():
    return datetime.now(tz=timezone.utc)


def get_str_timestamp():
    return get_processing_time().strftime("%d.%m.%Y")

# set dates for analysis
py_date = get_processing_time()
one_year_timedelta = timedelta(days=365)
five_year_timedelta = timedelta(days=(365 * 5))

processing_date = get_str_timestamp()

# Create list of dates for time series to look for more images around the initial date as the AOI is too large to be covered by one tile.
days_in_interval = 40

def get_timeframes():
    start_date = ee.Date(py_date.replace(year=2016, month=7, day=1))
    end_date = ee.Date(py_date)
    n_months = end_date.difference(start_date,'days').round()


    return  (n_months, {
        'two_weeks': {'start_date': ee.Date(py_date - timedelta(days=14)), 'end_date': end_date},
        'one_year': {'start_date': ee.Date(py_date - one_year_timedelta), 'end_date': end_date},
        'since_2016': {'start_date': ee.Date(py_date - five_year_timedelta), 'end_date': ee.Date(py_date)},
        'nov_2016': {'start_date': ee.Date(
            py_date.replace(year=py_date.year - 5, month=11, day=1) if py_date.replace(month=11, day=1) <= py_date else py_date.replace(year=py_date.year-6, month=11, day=1)
        ), 'end_date': ee.Date(
            py_date.replace(month=11, day=1) if py_date.replace(month=11, day=1) <= py_date else py_date.replace(year=py_date.year-1, month=11, day=1)
        )},
        'july_2016': {'start_date': ee.Date(
            py_date.replace(year=py_date.year - 5, month=7, day=1) if py_date.replace(month=7, day=1) <= py_date else py_date.replace(year=py_date.year-6, month=7, day=1)
        ), 'end_date': ee.Date(
            py_date.replace(month=7, day=1) if py_date.replace(month=7, day=1) <= py_date else py_date.replace(year=py_date.year-1, month=7, day=1)
        )},
    })

head_text = {
    'two_weeks': 'Short-term: One-week',
    'one_year': 'Medium-term: One-year',
    'since_2016': 'Long-term: Five-year',
    'nov_2016': 'Long-term: Five-year winter',
    'july_2016': 'Long-term: Five-year summer',
}

body_text = {
    'two_weeks': [
        'Direct irrigation, pruning and maintenance control for last two weeks',
        'Focus on areas under maintenance (parks, roads)'
    ],
    'one_year': [
        ' Trends in maintenance performance and construction for one year',
        ' Indicative of environmental changes (weather, groundwater)'
    ],
    'since_2016': [
        'Long-term trends in maintenance, construction, and environmental changes'
    ],
    'nov_2016': [
        ' Long-term trends in natural and managed vegetation in favourable weather'
    ],
    'july_2016': [
        'Long-term trends in natural and managed vegetation in heat and water stress'
    ]
}

growth_vis_params = {
    'min': -1,
    'max': 1,
    'palette': ['FF0000', '00FF00'],
}

geo_vis_params = {
    'opacity': 0.5,
    'palette': ['FFFFFF'],
}

cloud_vis_params = {
    'palette': ['FFFFFF'],
}


basemaps = {
    'Google Maps': folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Maps',
        overlay=True,
        control=True,
    ),
    'Google Satellite': folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite',
        overlay=True,
        control=True,
        control_scale=True,
    ),
    'Google Terrain': folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Terrain',
        overlay=True,
        control=True
    ),
    'Google Satellite Hybrid': folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite',
        overlay=True,
        control=True
    ),
    'Esri Satellite': folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satellite',
        overlay=True,
        control=True
    )
}

pdf_path_template = '{prefix}/output/' + datetime.now().strftime("%Y%m%d") + '-{name}-Vegetation-Cover-Report.pdf'
