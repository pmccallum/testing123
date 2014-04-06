import json
import utils
import hashlib
from elastic import es
import config as CONFIG
from random import randint
from bs4 import BeautifulSoup
from xml.etree import ElementTree


class Placemark():

    def __init__(self):
        self.open_data = {}
        self.geometry = []
        self.mbr_data = {}
        self.center = []
        self.type = None

    def save_placemark(self):
        es.index(index=CONFIG.ES_INDEX,
                 doc_type='item',
                 body=json.dumps({
                     'open_data': self.open_data,
                     'shape': self.geometry,
                     'mbr_data': self.mbr_data,
                     'center': self.center,
                     'type': self.type
                 }))

    @staticmethod
    def parse_geom_to_array(string):
        # Clean input
        string = str(string).strip(' ')

        # Try and read as if formatted as a polygon
        points = string.split(' ')

        # Create array for our final coordinates
        point_array = []

        # If it has less than four points, this is not a valid polygon
        if points.__len__() < 4:
            # This is not a polygon.
            axis = points[0].split(',')
            point_array.append([float(axis[1]), float(axis[0]), float(axis[2])])
        else:
            # This is a polygon...
            for point in points:
                coords = point.split(',')
                point_array.append([float(coords[1]), float(coords[0]), float(coords[2])])

        return point_array

    def calculate_mbr(self):
        coords = self.geometry

        nMost = None
        sMost = None
        eMost = None
        wMost = None

        for point in coords:
            for i, pos in enumerate(point):
                if i == 1:
                    if nMost == None or sMost == None:
                        nMost = pos
                        sMost = pos
                    else:
                        if pos > nMost:
                            nMost = pos
                        elif pos < sMost:
                            sMost = pos
                elif i == 0:
                    if eMost == None or wMost == None:
                        eMost = pos
                        wMost = pos
                    else:
                        if pos > eMost:
                            eMost = pos
                        elif pos < wMost:
                            wMost = pos
                elif i == 2:
                    # Skip Z coordinate
                    continue

        self.mbr_data['_mbr_nw_long'] = float(nMost)
        self.mbr_data['_mbr_nw_lat'] = float(wMost)

        self.mbr_data['_mbr_ne_long'] = float(nMost)
        self.mbr_data['_mbr_ne_lat'] = float(eMost)

        self.mbr_data['_mbr_se_long'] = float(sMost)
        self.mbr_data['_mbr_se_lat'] = float(eMost)

        self.mbr_data['_mbr_sw_long'] = float(sMost)
        self.mbr_data['_mbr_sw_lat'] = float(wMost)

    def calculate_center(self):
        self.center = utils.centroid_for_polygon(self.geometry)

# Prompt for input file
file_name = raw_input('Path to .kml file (absolute): ')

# Tell user that the program may appear to hang for a time
print 'Will now attempt to parse file, this may take a while...'

# Setup beautiful soup
namespace = 'http://www.opengis.net/kml/2.2'
dataset = ElementTree.parse(file_name)
root = dataset.getroot()

tree = './/{%s}Placemark' % (namespace)

placemarks = root.findall(tree)

i = 0

_pm_objects = []

for placemark in placemarks:
    i += 1

    _pm_objects.append(Placemark())

    pm = _pm_objects[_pm_objects.__len__() - 1]

    elemName = placemark.find('{%s}name' % namespace)

    polygon = []

    points = placemark.findall('.//{%s}coordinates' % namespace)

    if points is not None:
        polygon = points[0].text
    else:
        print 'No geometry found for current item'
        print pm
        for item in placemark.iter():
            print item
        exit()
        polygon = '0,0,0'

    elemDesc = placemark.find('{%s}description' % namespace).text
    htmlDesc = BeautifulSoup(elemDesc)
    tables = htmlDesc.findAll('td')

    geom = Placemark.parse_geom_to_array(polygon)

    if geom.__len__() > 1:
        # Is a polygon
        pm.geometry = geom
        pm.type = 'polygon'
        pm.calculate_center()
    else:
        # Is a point
        pm.geometry = geom
        pm.type = 'point'
        pm.center = geom[0]

    pm.calculate_mbr()

    for index, td in enumerate(tables):
        if index % 2 != 0:
            continue

        if index == 0:
            try:
                stuff = str(tables[index + 1].contents[1])

                subSoup = BeautifulSoup(stuff)

                subTables = subSoup.findAll('td', text=True)

                found = False

                for i2, td2 in enumerate(subTables):
                    if i2 % 2 != 0:
                        continue

                    _pm_objects[_pm_objects.__len__() - 1].open_data[td2.text] = subTables[i2 + 1].text

                del subTables
                del subSoup
            except:
                continue

print 'Found', i, 'placemarks.'

start_import_prompt = raw_input('Begin import? (y/n) [y]: ')

if start_import_prompt in ['', 'y']:
    pass
else:
    exit()

saved = 0

for index, pm in enumerate(_pm_objects):
    pm.save_placemark()

    saved += 1

print 'Import complete:', saved, 'inserted.'