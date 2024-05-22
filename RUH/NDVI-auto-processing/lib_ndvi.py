import logging
import bs4
import ee
import folium
import json
import geojson
import os
from PIL import Image
from pathlib import Path
from datetime import datetime, timezone
import selenium.webdriver
from selenium.webdriver.firefox.options import Options
import time
from send_email import sendEmail, open_project_date
from xhtml2pdf import pisa
from definitions import *
from shutil import copy
from pprint import pprint as pp


def add_data_to_html(source_html, logo, data, head_text, body_text):
    soup = bs4.BeautifulSoup(source_html, features="html5lib")
    html_logo = soup.new_tag('img', src=logo, id="header_content")
    soup.body.append(html_logo)

    project_name = data[list(data.keys())[0]]['project_name']
    headline = soup.new_tag('p', id="intro_headline")
    headline.string = project_name
    soup.body.append(headline)
    headline_two = soup.new_tag('p', id="intro_headline")
    headline_two.string = 'Vegetation Cover Change Report'
    soup.body.append(headline_two)
    date = soup.new_tag('p')
    date.string = processing_date
    soup.body.append(date)
    version = soup.new_tag('p', **{'class': 'version'})
    version.string = 'v1.1'
    soup.body.append(version)
    dear_all = soup.new_tag('p')
    dear_all.string = 'Dear all,'
    soup.body.append(dear_all)
    intro_text = soup.new_tag('p', **{'class': 'title_padding_under_intro'})
    intro_text.string = 'This report localises changes in vegetation health for five time periods, based on \
    available data. The maps show positive vegetation health changes gain in green, negative ones in red.'
    soup.body.append(intro_text)
    for timeframe in data.keys():
        bulletpoint_headline = soup.new_tag('p', id="bulletpoint_headline")
        bulletpoint_headline.string = f'{head_text[timeframe]} comparison \
        ({data[timeframe]["start_date_satellite"]} to {data[timeframe]["end_date_satellite"]})'
        soup.body.append(bulletpoint_headline)
        ul = soup.new_tag('ul')
        for bulletpoint in body_text[timeframe]:
            li = soup.new_tag('li')
            li.string = bulletpoint
            ul.append(li)
        soup.body.append(ul)
    regards = soup.new_tag('p', **{'class': 'kind_regards'})
    regards.string = 'Kind regards,'
    soup.body.append(regards)
    regards = soup.new_tag('p')
    regards.string = 'Boedeker Systems'
    soup.body.append(regards)
    # necessary for page break
    new_page = soup.new_tag('p', **{'class': 'new-page'})
    soup.body.append(new_page)
    for timeframe in data.keys():
        image_headline = soup.new_tag('p', id="image_headline")
        image_headline.string = f'{head_text[timeframe]} comparison \
        ({data[timeframe]["start_date_satellite"]} to {data[timeframe]["end_date_satellite"]})'
        soup.body.append(image_headline)
        ul = soup.new_tag('ul')

        area_paragraph = soup.new_tag('li')
        area_paragraph.string = f'Project area: {data[timeframe]["project_area"]:.3f} km²'
        ul.append(area_paragraph)

        cover_start = soup.new_tag('li')
        cover_start.string = f'Vegetation cover ({data[timeframe]["start_date_satellite"]}): \
        {data[timeframe]["vegetation_start"]:,.0f} m² ({data[timeframe]["vegetation_share_start"]:.2f} %)'
        ul.append(cover_start)

        cover_end = soup.new_tag('li')
        cover_end.string = f'Vegetation cover ({data[timeframe]["end_date_satellite"]}): \
        {data[timeframe]["vegetation_end"]:,.0f} m² ({data[timeframe]["vegetation_share_end"]:.2f} %)'
        ul.append(cover_end)

        veg_gain = soup.new_tag('li')
        veg_gain.string = f'Vegetation health increase (green): \
        {data[timeframe]["vegetation_gain"]:,.0f} m² ({data[timeframe]["vegetation_gain_relative"]:.2f} %)'
        ul.append(veg_gain)

        veg_loss = soup.new_tag('li')
        veg_loss.string = f'Vegetation health decrease (red): \
        {data[timeframe]["vegetation_loss"]:,.0f} m² ({data[timeframe]["vegetation_loss_relative"]:.2f} %)'
        ul.append(veg_loss)

        net_veg_change = soup.new_tag('li')
        net_veg_change.string = f'Net vegetation change: \
        {data[timeframe]["vegetation_end"] - data[timeframe]["vegetation_start"]:,.0f} m² \
        ({data[timeframe]["vegetation_share_end"] - data[timeframe]["vegetation_share_start"]:.2f} %)'
        ul.append(net_veg_change)

        soup.body.append(ul)

        png = data[timeframe]['path']
        try: 
            jpeg = Path(png).with_suffix('.jpeg')
            html_img = soup.new_tag('img', src=jpeg)
        except Exception as e:
            html_img = soup.new_tag('img', src=png)
            print(f"Error compressing PNG: {str(e)}. \n Falling back to the raw image")
        img_formatting = soup.new_tag('div', id="img_format")
        img_formatting.append(html_img)
        soup.body.append(img_formatting)

        # necessary for page break
        new_page = soup.new_tag('p', **{'class': 'new-page'})
        soup.body.append(new_page)
    return soup


def maskS2clouds(image):
    # Function to mask clouds using the Sentinel-2 QA band param {ee.Image} image Sentinel-2 image @return {ee.Image} cloud masked Sentinel-2 image
    qa = image.select('QA60')

    # Bits 10 and 11 are clouds and cirrus, respectively.
    cloudBitMask = ee.Number(2).pow(10).int()
    cirrusBitMask = ee.Number(2).pow(11).int()

    # Both flags should be set to zero, indicating clear conditions.
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))

    image = image.updateMask(mask)
    return image


# NDVI function
def add_NDVI(image, geometry_feature):
    # for the area we assume the pixels are 10x10m also we know that there is up to 0.01% variance due to the projection used. This can be improved by using areaPixel = ndvi.multiply(ee.Image.pixelArea()).rename('area_m2')
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('ndvi')
    thres = ndvi.gte(0.2).rename('thres')
    ndvi02_area = thres.multiply(ee.Image.pixelArea()).rename('ndvi02_area')

    # calculate ndvi > 0.2 area
    ndviStats = ndvi02_area.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=geometry_feature,
        scale=10,
        maxPixels=1e29
    )

    image = image.set(ndviStats)

    # calculate area of AOI
    area = image.select('B1').multiply(0).add(1).multiply(ee.Image.pixelArea()).rename('area')

    # calculate area
    img_stats = area.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=geometry_feature,
        scale=10,
        maxPixels=1e29
    )

    image = image.set(img_stats)
    image = image.addBands(thres)
    return image


def add_ee_layer(self, ee_object, vis_params, name):
    """Adds a method for displaying Earth Engine image tiles to folium map."""
    try:
        # display ee.Image()
        if isinstance(ee_object, ee.image.Image):
            map_id_dict = ee.Image(ee_object).getMapId(vis_params)
            folium.raster_layers.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name=name,
                overlay=True,
                control=True
            ).add_to(self)

        # display ee.ImageCollection()
        elif isinstance(ee_object, ee.imagecollection.ImageCollection):
            ee_object_new = ee_object.mosaic()
            map_id_dict = ee.Image(ee_object_new).getMapId(vis_params)
            folium.raster_layers.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name=name,
                overlay=True,
                control=True
            ).add_to(self)

        # display ee.Geometry()
        elif isinstance(ee_object, ee.geometry.Geometry):
            folium.GeoJson(
                data=ee_object.getInfo(),
                name=name,
                overlay=True,
                control=True
            ).add_to(self)

        # display ee.FeatureCollection()
        elif isinstance(ee_object, ee.featurecollection.FeatureCollection):
            ee_object_new = ee.Image().paint(ee_object, 0, 2)
            map_id_dict = ee.Image(ee_object_new).getMapId(vis_params)
            folium.raster_layers.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name=name,
                overlay=True,
                control=True
            ).add_to(self)

    except Exception as e:
        print(f"Could not display {name}. Exception: {e}")

def convert_png_to_jpg(img_path):
    print(f"Image: {img_path}, size: {os.path.getsize(img_path)}")
    new_image_path = Path(img_path).with_suffix(".jpeg")
    img_copy_path = Path(img_path).with_suffix(".temp.png")
    copy(img_path, img_copy_path)
    tmp = Image.open(img_copy_path).convert('RGB')
    tmp.save(new_image_path)
    os.remove(img_copy_path)
    return new_image_path


def convert_html_to_pdf(source_html, output_filename):
    # open output file for writing (truncated binary)
    result_file = open(output_filename, "w+b")
    try:
        # convert HTML to PDF
        pisa_status = pisa.CreatePDF(
            source_html,  # the HTML to convert
            dest=result_file)  # file handle to receive result
    except Exception as e:
        print(f'Error: {e}')
        logging.debug(e)
    finally:
        # close output file
        result_file.close()  # close output file

    # return False on success and True on errors
    return pisa_status.err


## Mosaic function
def CreateMosaic(d1, geometry_feature):
    days_in_interval = 40
    start = ee.Date(d1)
    end = ee.Date(d1).advance(days_in_interval, 'days')
    date_range = ee.DateRange(start, end)
    name = start.format('YYYY-MM-dd').cat(' to ').cat(end.format('YYYY-MM-dd'))

    ic = (ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
        .filterDate(date_range)
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 1))
        .filterBounds(geometry_feature)
        .map(lambda image: image.clip(geometry_feature))
        .mosaic())

    return ic.set(
        "system:time_start", start.millis(),
        "system:id", start.format("YYYY-MM-dd"),
        "name", name,
        "range", date_range)


def GenerateReport(collection, timeframe_delta, geometry_feature, screenshot_save_name, project_name):
    timeframe_collection = collection.filterDate(timeframe_delta['start_date'], timeframe_delta['end_date'])
    ndvi_timeframe_collection = timeframe_collection.map(lambda x: add_NDVI(x, geometry_feature))
    ndvi_img_start = ee.Image(ndvi_timeframe_collection.toList(ndvi_timeframe_collection.size()).get(0))
    ndvi_img_end = ee.Image(ndvi_timeframe_collection.toList(ndvi_timeframe_collection.size()).get(ndvi_timeframe_collection.size().subtract(1)))

    # if there is no different image within that timeframe just take the next best
    if timeframe_collection.size().getInfo() > 1:
        latest_image = ee.Image(timeframe_collection.toList(timeframe_collection.size()).get(timeframe_collection.size().subtract(1)))
        first_image = ee.Image(timeframe_collection.toList(timeframe_collection.size()).get(0))

        latest_image_date = latest_image.date().format("dd.MM.YYYY").getInfo()
        first_image_date = first_image.date().format("dd.MM.YYYY").getInfo()
    else:
        latest_image = ee.Image(collection.toList(collection.size()).get(collection.size().subtract(1)))
        first_image = ee.Image(collection.toList(collection.size()).get(collection.size().subtract(2)))

        latest_image_date = latest_image.date().format("dd.MM.YYYY").getInfo()
        first_image_date = first_image.date().format("dd.MM.YYYY").getInfo()

        ndvi_img_start = ee.Image(add_NDVI(first_image, geometry_feature))
        ndvi_img_end = ee.Image(add_NDVI(latest_image, geometry_feature))

    # prepare values for report
    project_area = ndvi_img_start.getNumber('area').getInfo()

    vegetation_start = ndvi_img_start.getNumber('ndvi02_area').getInfo()
    vegetation_end = ndvi_img_end.getNumber('ndvi02_area').getInfo()

    area_change = (vegetation_end-vegetation_start)

    relative_change = 100 - (vegetation_end/vegetation_start) * 100
    vegetation_share_start = (vegetation_start/project_area) * 100
    vegetation_share_end = (vegetation_end/project_area) * 100
    vegetation_share_change = vegetation_share_end - vegetation_share_start

    # Calculate difference between the two datasets
    growth_decline_img = ndvi_img_end.subtract(ndvi_img_start).select('thres')
    growth_decline_img_mask = growth_decline_img.neq(0)
    growth_mask = growth_decline_img.eq(1)
    growth_img = growth_decline_img.updateMask(growth_mask)
    growth_decline_img = growth_decline_img.updateMask(growth_decline_img_mask)

    # Calculate area
    vegetation_stats_gain = growth_img.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=geometry_feature,
        scale=10,
        maxPixels=1e29)

    vegetation_gain = ee.Number(vegetation_stats_gain.get('thres')).multiply(100).round().getInfo()

    vegetation_loss = area_change - vegetation_gain
    vegetation_loss_relative = -vegetation_loss / project_area * 100
    vegetation_gain_relative = vegetation_gain / project_area * 100

    if area_change < 0:
        relative_change = -relative_change

    
    return {
        "report": {
            'start_date': timeframe_delta['start_date'].format("dd.MM.YYYY").getInfo(),
            'end_date': timeframe_delta['end_date'].format("dd.MM.YYYY").getInfo(),
            'start_date_satellite': first_image_date,
            'end_date_satellite': latest_image_date,
            'vegetation_start': vegetation_start,
            'vegetation_end': vegetation_end,
            'vegetation_share_start': vegetation_share_start,
            'vegetation_share_end': vegetation_share_end,
            'vegetation_share_change': vegetation_share_change,
            'project_area': project_area/(1000*1000),
            'area_change': area_change,
            'relative_change': relative_change,
            'vegetation_gain': vegetation_gain,
            'vegetation_loss': vegetation_loss,
            'vegetation_gain_relative': vegetation_gain_relative,
            'vegetation_loss_relative': vegetation_loss_relative,
            'path': screenshot_save_name,
            'project_name': project_name,
        },
        "growth_decline_img": growth_decline_img
    }

def _SaveMap(geo_data, growth_decline_img, screenshot_save_name): 
    coords = list(geojson.utils.coords(geo_data))
    starting_coord = [*coords[0]]
    print(starting_coord)
    merged_poly =  {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [[[[*i] for i in coords]]]
        }
    }

    merged_poly["geometry"]["coordinates"][0][0].append(starting_coord)

    swapped_coords = [[x[1], x[0]] for x in coords]
    
    html_map = 'map.html'

    # Define center of our map
    centroid = ee.Geometry(merged_poly["geometry"]).centroid().getInfo()['coordinates']

    # get coordinates from centroid for folium
    lat, lon = centroid[1], centroid[0]
    my_map = folium.Map(location=[lat, lon], zoom_control=False, control_scale=True)
    basemaps['Google Satellite'].add_to(my_map)

    for feature in geo_data["features"]:
        white_polygon = ee.geometry.Geometry(geo_json=feature["geometry"])
        my_map.add_ee_layer(white_polygon, geo_vis_params, 'Half opaque polygon')
        my_map.add_ee_layer(growth_decline_img, growth_vis_params, 'Growth and decline image')

    # fit bounds for optimal zoom level
    my_map.fit_bounds(swapped_coords)

    my_map.save(html_map)

    options = Options()
    options.add_argument('--headless')

    driver = selenium.webdriver.Firefox(options=options)
    driver.set_window_size(1200, 1200)

    driver.get(f'file:///{os.path.dirname(os.path.abspath("map.html"))}\\map.html')
    time.sleep(5)
    if driver.save_screenshot(screenshot_save_name):
        print(f"Screenshot successful: {screenshot_save_name}")
    
    driver.quit()
    # discard temporary data
    os.remove(html_map)


def SaveMap(geo_data, growth_decline_img, screenshot_save_name): 
    success = False
    while not success:
        if os.path.exists(screenshot_save_name):
            print("Retrying screenshot")
            os.remove(screenshot_save_name)
        try:
            _SaveMap(geo_data, growth_decline_img,  screenshot_save_name)
            jpeg = convert_png_to_jpg(Path(screenshot_save_name).resolve())
            print(f"jpeg name: {jpeg}")
            success = True
        except Exception as e:
            print(f"Retrying screenshot due to: {e}")
            success = False

def SaveReport(
        json_file_name, 
        latest_image_date, 
        timeframe_name, 
        res,
        geo_data, 
        ):
    new_report = False
    with open(json_file_name, 'r', encoding='utf-8') as f:
        data = {}
        try:
            data = json.load(f)
        except:
            # if the json is unreadable for any reason, it'll be created later anyway
            pass
        report = res["report"]
        potential_duplicate = None
        if data != {}: 
            potential_duplicate = data[list(data.keys())[-1]]\
                .get(timeframe_name, {'end_date_satellite': None})\
                .get('end_date_satellite') 
        if latest_image_date != potential_duplicate:
            if data != {}:
                print(f'Newest available data is from {latest_image_date}. Last generated report is from: {potential_duplicate}')
            new_report = True
            tmp = data.get(processing_date, {})
            tmp[timeframe_name] = report 
            data[processing_date] = tmp
            SaveMap(
                geo_data, 
                res["growth_decline_img"],
                report["path"]
            )
        else:
            print(f'No new data for {processing_date}.')
    with open(json_file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return new_report

def GeneratePdf(data, report, logo_path, source_html_path, pdf_path):
    # print(data)
    logo = Path(logo_path).resolve()
    with open(source_html_path, 'r') as html_text:
        source_html = html_text.read()

    _, timeframes = get_timeframes()
    for timeframe in timeframes:

        # if no data for timeframe
        if timeframe not in data[processing_date].keys():
            data[processing_date][timeframe] = {}
            # search for previous date that has the data
            for date in list(data.keys())[-2::-1]:
                # fill data in
                if timeframe in data[date].keys():
                    data[processing_date][timeframe] = data[date][timeframe]

    # sort data before generating report
    data[processing_date] = {k: data[processing_date][k] for k in list(timeframes.keys())}

    with open(report["path"], 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

    soup = add_data_to_html(
        source_html, 
        logo, 
        data[processing_date], 
        head_text, 
        body_text, 
    )
    pisa.showLogging()
    convert_html_to_pdf(soup.prettify(), pdf_path)

def ProcessCollection(
        collection, 
        geo_data, 
        json_path, 
        screenshot_save_name_base
    ):
    name = geo_data["name"]
    geometry_feature = ee.FeatureCollection(geo_data)
    image_list = []
    new_report = False
    _, timeframes = get_timeframes()
    for timeframe_name, timeframe_delta in timeframes.items():
        screenshot_save_name = f'{screenshot_save_name_base}_{processing_date}_{timeframe_name}.png'
        print(f"Generating report for {timeframe_name} for {name}")
        res = GenerateReport(
            collection=collection, 
            timeframe_delta=timeframe_delta, 
            geometry_feature=geometry_feature,
            screenshot_save_name=screenshot_save_name,
            project_name=geo_data["name"]
            )
        report = res["report"]
        first_image_date =  datetime.strptime(report["start_date_satellite"], "%d.%m.%Y")
        latest_image_date = datetime.strptime(report["end_date_satellite"], "%d.%m.%Y")

        if timeframe_name == 'two_weeks':
            week_diff = (latest_image_date - first_image_date).days / 7.0
            htext = f"{week_diff}-weeks" if week_diff > 1 else "One-week"
            btext = f"{week_diff} weeks" if week_diff > 1 else "last week"
            head_text['two_weeks'] = f'Short-term: {htext}'
            body_text['two_weeks'] = [
                f'Direct irrigation, pruning and maintenance control for the last {btext} weeks',
                'Focus on areas under maintenance (parks, roads)'
            ]
        # swap the coordinates because folium takes them the other way around
        new_report |= SaveReport(
            json_path, 
            report["start_date_satellite"], 
            timeframe_name, 
            res,
            geo_data=geo_data,  
            )
        if new_report:
            image_list.append(report["path"])

        print(f'timeframe: {timeframe_name} processed')
    return (image_list, report, new_report)

def email(
        credentials_path, 
        json_file_name, 
        new_report, 
        data, 
        pdf_path, 
        local_test_run=False, 
        email_test_run=False, 
        send_test=False
):
    if credentials_path is None:
        return 

    project_data = open_project_date(json_file_name)
    key = list(data.keys())[-1] if email_test_run else processing_date
    if not local_test_run and new_report:
        sendEmail(send_test, project_data[key], credentials_path, pdf_path)
        tmp = "No" if new_report else "New"
        logging.debug(f'{tmp} new email on {str(datetime.today())}')


def ProcessFeature(
    collection,
    geo_data,
    json_file_name,
    screenshot_save_name_base,
    credentials_path,
    report_html,
    logo,
    local_test_run,
    email_test_run
):
    data = {}
    with open(json_file_name, 'a', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except:
            pass
    
    new_report = False

    _, report, new_report = ProcessCollection(
        collection=collection, 
        geo_data=geo_data, 
        json_path=json_file_name,
        screenshot_save_name_base=screenshot_save_name_base
    )

    pdf_prefix = '..' if local_test_run else 'RUH'
    pdf_path = Path(pdf_path_template.format(prefix=pdf_prefix, name=geo_data["name"]))
    
    pdf_path.parent.resolve().mkdir(exist_ok=True, parents=True)

    # get fresh data
    with open(json_file_name, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if new_report:
        GeneratePdf(
            data=data, 
            report=report, 
            logo_path=logo, 
            source_html_path=report_html, 
            pdf_path=pdf_path
            )


    email(
        credentials_path=credentials_path,
        json_file_name=json_file_name,
        new_report=new_report,
        data=data,
        pdf_path=pdf_path,
        local_test_run=local_test_run,
        email_test_run=email_test_run,
    )


def Run(
    geojson_path,
    screenshot_save_name_base,
    json_folder,
    credentials_path,
    report_html,
    logo,
    local_test_run,
    email_test_run
):
    with open(geojson_path, "r") as f:
        geo_data = json.load(f)

    folium.Map.add_ee_layer = add_ee_layer

    ### calculate NDVI
    n_months, _ = get_timeframes()
    dates = ee.List.sequence(0, n_months, days_in_interval)
    dates = dates.map(lambda x: ee.Date(py_date.replace(year=2016, month=7, day=1)).advance(x, 'days'))

    geo_data_arr = [
        {
            "type": geo_data["type"],
            "crs": geo_data["crs"],
            "features": [i],
            "name": i["properties"]["REF_CL_CAT"]
        }
        for i in geo_data["features"]
    ]
        
    ### maps and report
    for feature in geo_data_arr:
        geometry_feature = ee.FeatureCollection(feature)
        collection = ee.ImageCollection(dates.map(lambda x: CreateMosaic(x, geometry_feature)))
        snake_case_name = feature["name"].lower().replace(' ', '_')
        json_file_name = os.path.join(json_folder, f"{snake_case_name}.json")
        ProcessFeature(
            collection=collection,
            geo_data=feature,
            json_file_name=json_file_name,
            screenshot_save_name_base=f"{snake_case_name}_{screenshot_save_name_base}",
            credentials_path=credentials_path,
            report_html=report_html,
            logo=logo,
            local_test_run=local_test_run,
            email_test_run=email_test_run
        )
