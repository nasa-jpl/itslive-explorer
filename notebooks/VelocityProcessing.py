import gc
import logging
import operator
from glob import glob

import geojson
import geopandas
import numpy as np
import pandas as pd
import rioxarray
import xarray as xr
from shapely.geometry import Polygon, box

logger = logging.getLogger('PROCESSING')


class VelocityProcessing:

    Version = '0.1.0'

    @staticmethod
    def box_to_geojson(coords: list):
        b = box(*coords)
        coords = [[c[0],c[1]] for c in list(b.exterior.coords)]
        return {
            'type': 'Polygon',
            'coordinates': [coords]
        }

    @staticmethod
    def coords_to_bbox(coords: list):
        """
        returns a bbox array for a given polygon
        """
        x_coordinates, y_coordinates = zip(*coords)
        return [(min(x_coordinates), min(y_coordinates)), (max(x_coordinates), max(y_coordinates))]

    @staticmethod
    def polygon_to_geojson(coords: list):
        coords = [[c[0],c[1]] for c in coords]
        return {
            'type': 'Polygon',
            'coordinates': [coords]
        }

    @staticmethod
    def load_cube(directory: str=None,
                  clip_geom: dict=None,
                  include_all_projections: bool=False):
        mid_date = []
        clipped_geometries = []
        paths = sorted(glob(directory))
        datasets = [xr.open_dataset(p) for p in paths]

        for ds in datasets:
            ds.coords['time'] = pd.to_datetime(ds.img_pair_info.date_center)
            # Keeps track of repeated mid-dates
            if ds.img_pair_info.date_center not in mid_date:
                mid_date.append(ds.img_pair_info.date_center)
                if 'UTM_Projection' in ds:
                    proj_var = 'UTM_Projection'
                    projection = int(ds.UTM_Projection.spatial_epsg)
                else:
                    proj_var = 'Polar_Stereographic'
                    projection = int(ds.Polar_Stereographic.spatial_epsg)

                ds = ds.drop_vars(['img_pair_info', proj_var])
                ds = ds.rio.write_crs(projection)
                try:
                    clipped_geom = ds.rio.clip([clip_geom], crs='epsg:4326')
                    # Keep only those layers with some velocity information
                    if not np.isnan(clipped_geom.v.max().values):
                        clipped_geometries.append(clipped_geom)
                except Exception as e:
                    logger.info('Out of bounds: ', e)
            else:
                logger.info('Repeated middate, skipping')
        del datasets
        gc.collect()
        if len(clipped_geometries) < 2:
            logger.warning('Not enough valid layers were found to create a cube')
            return None
        projections = {}
        projections_counts = {}
        for geo in clipped_geometries:
            if str(geo.rio.crs) in projections:
                projections[str(geo.rio.crs)].append(geo)
                projections_counts[str(geo.rio.crs)] += 1
            else:
                projections[str(geo.rio.crs)] = [geo]
                projections_counts[str(geo.rio.crs)] = 1
        sorted_projections = sorted(projections_counts.items(), key=operator.itemgetter(1))
        most_common = sorted_projections[-1]
        less_common = sorted_projections[0]
        most_common_key = most_common[0]
        less_common_key = less_common[0]

        stacked_projections = {}
        if include_all_projections is False:
            return xr.concat(projections[most_common_key], dim='time').sortby('time')
        if len(projections_counts) > 2:
            less_common = sorted_projections[1]
            logger.warning(f'more than one projection found, merging only the 2 most common ones {most_common_key} and {less_common_key}')
        for k in projections:
            stacked_projections[k] = xr.concat(projections[k], dim='time').sortby('time')
        # vx and vy may have errors as they need to be reprojected as well.
        less_common_reprojected = stacked_projections[less_common_key].rio.reproject_match(
            stacked_projections[most_common_key])
        less_common_reprojected.v.values[less_common_reprojected.v.values < 0] = np.nan
        less_common_reprojected.vx.values[less_common_reprojected.vx.values < 0] = np.nan
        less_common_reprojected.vy.values[less_common_reprojected.vy.values < 0] = np.nan
        return xr.concat([less_common_reprojected, stacked_projections[most_common_key]], dim='time')

    @staticmethod
    def plot_cube(cube:str):
        return None


