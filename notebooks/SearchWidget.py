import calendar
import json
import os
from datetime import datetime
from uuid import uuid4

import ipywidgets as widgets
import pandas as pd
import requests
from bqplot import Axis, DateScale, Figure, LinearScale, Lines
from ipyleaflet import DrawControl, GeoJSON, LayersControl, Map
from IPython.display import display
from pqdm.threads import pqdm
from projections import projections
from shapely.geometry import box
from sidecar import Sidecar


class map():
    """
    Widget to access ITS_LIVE image pairs.
    """
    def __init__(self, hemisphere='global', orientation='horizontal'):
        """
        start_date: fixed to 1984 when the pair processing starts
        end_date: now eventually but processing is behind a year.
        min_separation: minimum number of days between image pairs
        max_separation: maximum number of days between image pairs
        min_coverage: percentage of valid glacier pixels
        geometry: current map selection
        hemisphere: current projection
        """
        self.properties = {
            'start_date': datetime(1993, 1, 1),
            'end_date': datetime.now(),
            'min_separation': 7,
            'max_separation': 365,
            'min_coverage': 1,
            'geometry': None,
            'hemisphere': hemisphere,
            'orientation': orientation,
            'max_granules_per_year': 1000,
            'project_name': 'default',
            'selected_months': []
        }
        self.granules_coverage = None
        self.granules_urls = None
        self.filtered_urls = []
        self._out = widgets.Output(layout={'border': '1px solid black'})

    def _create_controls(self):
        self.controls = []
        self._control_dc = DrawControl(
            edit=False,
            remove=False,
            polyline={},
            circlemarker={},
            polygon={
                "shapeOptions": {
                    "fillColor": "#fca45d",
                    "color": "#cc00cc",
                    "fillOpacity": 0.5
                },
                "allowIntersection": False
            },
            rectangle={
                "shapeOptions": {
                    "fillColor": "#cc00cc",
                    "color": "#cc00cc",
                    "fillOpacity": 0.5
                }
            })
        slider_dates = [(date.strftime(' %Y-%m-%d '), date) for date in
                        pd.date_range(datetime(1993, 1, 1),
                                      datetime.now(),
                                      freq='D')]

        slider_index = (0, len(slider_dates) - 1)

        self._control_selected_months = widgets.SelectMultiple(
            options=[calendar.month_name[m] for m in range(1,13)],
            value=self.properties['selected_months'],
            description='Selected months (mid-date): ',
            disabled=False,
            style={'max_width': '100px', 'display': 'flex-start',
                    'description_width': 'initial'}
        )

        self._control_projection = widgets.Dropdown(
            options=['global', 'south', 'north'],
            description='Hemisphere:',
            disabled=False,
            value=self.properties['hemisphere']
        )
        self._control_dates_range = widgets.SelectionRangeSlider(
            options=slider_dates,
            index=slider_index,
            continuous_update=False,
            description='Date Range',
            orientation='horizontal',
            layout={'width': '80%',
                    'max_with': '90%',
                    'display': 'flex-start',
                    'description_width': 'initial'})
        self._control_coverage = widgets.Dropdown(
            options=[1, 10, 20, 30, 40, 50, 60, 70, 80, 90],
            value=self.properties['min_coverage'],
            description='Minimum coverage percentage:',
            disabled=False,
            style={'width': 'max-content',
                   'display': 'flex-start',
                   'description_width': 'initial'}
        )
        self._control_min_separation = widgets.Dropdown(
            options=['any', 7, 30, 60, 90, 120, 180, 365],
            value=self.properties['min_separation'],
            description='Min: ',
            disabled=False,
            layout={'max_width': '20%', 'display': 'flex-start'}
        )
        self._control_max_separation = widgets.Dropdown(
            options=['any', 7, 30, 60, 90, 120, 180, 365],
            value=self.properties['max_separation'],
            description='Max: ',
            disabled=False,
            layout={'max_width': '20%', 'display': 'right'}
        )
        self._control_separation = widgets.HBox([widgets.Label('Days between image pairs:'),
                                                self._control_min_separation,
                                                self._control_max_separation])
        self._control_layers = LayersControl(position='topright')

        self._control_get_urls_button = widgets.Button(
            description='1. Search',
            disabled=False,
            button_style='info',
            style={'display': 'flex-end'},
            tooltip='Get a list of velocity-pair granules using the current parameters into the granule_urls attribute'
            # icon='fa-spinner'
        )
        self._control_filter_button = widgets.Button(
            description=' 2. Apply filters',
            disabled=False,
            button_style='info',
            tooltip='Apply max granules per year and month selection filters to the granule_urls list'
            # icon='fa-spinner'
        )
        self._control_download_button = widgets.Button(
            description=' 3. Download granules',
            disabled=False,
            button_style='info',
            tooltip='Download the selected velocity-pair granules into the data directory.'
            # icon='fa-spinner'
        )
        self._control_max_files_per_year = widgets.Text(
            placeholder='e.g. 10',
            value=str(self.properties['max_granules_per_year']),
            description='Max granules per year:',
            disabled=False,
            style={'max_width': '40px',
                   'display': 'flex-start',
                   'description_width': 'initial'}
        )
        self._control_filters = widgets.Accordion(children=[
            widgets.HBox([
                self._control_filter_button,
                self._control_selected_months,
                self._control_max_files_per_year,
        ])], selected_index=None)
        self._control_selected_granules =  widgets.Label(
            value=f'Selected Granules: {len(self.filtered_urls)}'
        )
        self._control_filters.set_title(0, 'Filters')

        self._control_download_project_name = widgets.Text(
            placeholder='e.g. pine-glacier-1990-2000',
            value=str(self.properties['project_name']),
            description='Project name: ',
            disabled=False,
            style={'max_width': '40px',
                   'display': 'flex-start',
                   'description_width': 'initial'}
        )

        self._control_api_search = widgets.Accordion(children=[
            widgets.VBox([
                self._control_projection,
                self._control_dates_range,
                self._control_coverage,
                self._control_separation,
                self._control_get_urls_button
        ])])
        self._control_api_search.set_title(0, 'Velocity-Pair Search Criteria')

        self._control_download_group = widgets.Accordion(
            children=[widgets.HBox([
                        widgets.VBox([
                            self._control_download_button,
                            self._control_selected_granules]
                        ),
                        self._control_download_project_name])],
            selected_index=None

        )
        self._control_download_group.set_title(0, 'Download data')


        self.controls.extend([self._control_api_search,
                              self._control_filters,
                              self._control_download_group
                              ])

    def _create_map(self, projection):
        projection = projections[projection]
        self.map = Map(center=projection['center'],
                       zoom=projection['zoom'],
                       max_zoom=projection['max_zoom'],
                       basemap=projection['base_map'],
                       crs=projection['projection'])
    # Events

    def _set_state(self):
        """
        keeps the state of the widgets after recreating them, once we get a projection
        control in the map this will not be necessary.
        """
        self.properties = {
            'start_date': self._control_dates_range.value[0],
            'end_date': self._control_dates_range.value[1],
            'min_separation': self._control_min_separation.value,
            'max_separation': self._control_max_separation.value,
            'min_coverage': self._control_coverage.value,
            'geometry': self.properties['geometry'],
            'hemisphere': self._control_projection.value,
            'max_granules_per_year': int(self._control_max_files_per_year.value),
            'selected_months': self._control_selected_months.value,
            'orientation': self.properties['orientation'],
            'project_name': self.properties['project_name']
        }

    def _change_hemisphere(self, event):
        if event['type'] == 'change' and event['name'] == 'value':
            self.properties['hemisphere'] = self._control_projection.value
            self.display(self._control_projection.value)

    def _change_selection(self, target, action, geo_json):
        if self.properties['geometry'] is not None:
            self.map.remove_layer(self.properties['geometry'])
        self.properties['geometry'] = GeoJSON(name='Selection', data=geo_json)
        self._control_dc.clear()
        self.map.add_layer(self.properties['geometry'])
        return None

    def _download_granules(self, e):
        self._control_download_button.icon = 'spinner'
        self._control_download_button.disabled = True
        #  def download_velocity_granules(self, urls, path_prefix=None, params=None, start=0, end=-1, threads=8):
        self.downloaded_files = self.download_velocity_granules(self.filtered_urls,
                                                                path_prefix=f'data/{self._control_download_project_name.value}',
                                                                params=self.get_current_selection())
        self._control_download_button.icon = 'check'
        self._control_download_button.disabled = False
        return None

    def _bind_widgets(self):
        self._control_dc.on_draw(self._change_selection)
        self.map.add_control(self._control_dc)
        self.map.add_control(self._control_layers)
        self._control_projection.observe(self._change_hemisphere)
        self._control_get_urls_button.on_click(self._fetch_urls)
        self._control_filter_button.on_click(self._apply_filters)
        self._control_download_button.on_click(self._download_granules)

    def _apply_filters(self, e):
        if self.granule_urls is not None:
            months = list(self._control_selected_months.value)
            if self._control_max_files_per_year.value == None or 0:
                max_files_per_year = None
            else:
                max_files_per_year = int(self._control_max_files_per_year.value)
            filtered_urls = self.filter_urls(self.granule_urls,
                                             months=months,
                                             max_files_per_year=max_files_per_year)
            self._control_selected_granules.value = f'Selected Granules: {len(self.filtered_urls)}'

            years = []
            counts = []
            for year in filtered_urls:
                counts.append(len(filtered_urls[year]))
                years.append(year)
            self.granules_coverage = {
                'years': years,
                'counts': counts
            }
            self._control_filter_button.icon = 'check'
            self.display(self.properties['hemisphere'])
            self._control_api_search.selected_index = None
            self._control_filters.selected_index = None


    def _get_temporal_coverage(self, url):
        file_name = url.split('/')[-1].replace('.nc', '')
        file_components = file_name.split('_')
        start_date = datetime.strptime(file_components[11], "%Y%m%d").date()
        end_date = datetime.strptime(file_components[3], "%Y%m%d").date()
        mid_date = start_date + (end_date - start_date) / 2

        coverage = {
            'url': url,
            'start': start_date,
            'end': end_date,
            'mid_date': mid_date
        }
        return coverage


    def _fetch_granule_counts(self, e):
        if self.properties['geometry'] is None:
            return None
        query_params = self.build_query_params()
        url = f'https://nsidc.org/apps/itslive-search/velocities/coverage/?{query_params}'
        print(f'querying: {url}')
        coverage = requests.get(url).json()
        years = []
        counts = []
        for year in coverage:
            counts.append(year['count'])
            years.append(year['year'])
        self.granules_coverage = {
            'years': years,
            'counts': counts
        }
        self.granule_count = sum(counts)
        return self.granules_coverage

    def _fetch_urls(self, e):
        if self.properties['geometry'] is None:
            return None

        self._control_get_urls_button.icon = 'fa-spinner'
        self._control_get_urls_button.disabled = True
        query_params = self.build_query_params()
        url = f'https://nsidc.org/apps/itslive-search/velocities/urls/?{query_params}&serialization=json'
        print(f'querying: {url}')
        urls =  [item['url'] for item in requests.get(url).json()]
        self.granule_urls = urls
        self._fetch_granule_counts(None)
        self.filtered_urls = self.granule_urls
        self.display(self.properties['hemisphere'])
        self._control_api_search.selected_index = None
        self._control_get_urls_button.icon = 'check'
        self._control_get_urls_button.disabled = False
        return urls

    def _draw_counts(self):
        if self.granules_coverage is None:
            return None
        cov = self.granules_coverage
        x_date = LinearScale()
        y_linear = LinearScale()
        line = Lines(x=cov['years'], y=cov['counts'],
                     scales={'x': x_date, 'y': y_linear},
                     labels=[f'Total Granules: {len(self.filtered_urls):,}'],
                     colors=["dodgerblue"],
                     display_legend=True)
        ax_x = Axis(scale=x_date, label="Date", grid_lines="solid", )
        ax_y = Axis(scale=y_linear, label="Count", orientation="vertical", grid_lines="solid")

        fig = Figure(marks=[line],
                     axes=[ax_x, ax_y],
                     legend_location="top-left",
                     title="Granule counts per year for selected area",)
        fig.layout.height = '300px'
        fig.layout.width = '100%'
        return fig


    # Public functions

    @staticmethod
    def Search(params: dict):
        """
        params:
            - params: dictionary with ITS_LIVE API parameters
                bbox or polygon: defines the area
                start: start time YYYY-mm-dd
                end: end time YYYY-mm-dd
                mission: include only a given mission(platform) i.e. LC08 (Landsat 8)
                min_interval: minimum time separation in days between image pairs
                max_interval: maximum separation in days between image pairs
                percent_valid_pixels: minimum valid glacier pixel coverage in percentage (quality of product)
                serialization: response format: json, text, html
                compressed: zip the response, default = False
        returns:
            - a list of velocity pair URLs that overalp with our parameters.
        example:
            - params = {
                'bbox': '10,20,30,20',
                'start': '2001-11-30',
                'end': '2018-01-01',
                'percent_valid_pixels': 60
              }
              granules = SearchWidget.search(params)
        """
        if 'polygon' in params:
            geometry_query = f"polygon={params['polygon']}&"
        else:
            geometry_query = f"bbox={params['bbox']}&"
        if 'mission' in params:
            mission_query = f"&mission={params['mission']}"
        else:
            mission_query = ""
        querystring = f"""
        {geometry_query}
        start={params['start']}&
        end={params['end']}&
        percent_valid_pixels={params['percent_valid_pixels']}&
        min_interval={params['min_separation']}&
        max_interval={params['max_separation']}
        {mission_query}
        """.replace('\n', '').replace('  ', '')

        query_url = f'https://nsidc.org/apps/itslive-search/velocities/urls/?{querystring}'
        print(f'Querying: {query_url}')
        try:
            res =  [item['url'] for item in requests.get(query_url).json()]
        except Exception as e:
            print(query_url, e)
            return None
        return res


    def filter_urls(self,
                    urls: list=None,
                    max_files_per_year: int=None,
                    months: list=None,
                    by_year: bool=True):
        """
        Helper functio to filter a list of URLS from ITS_LIVE on witch the mid-date matches the months given
        in the `months` parameter up to a max number of files per year. i.e. if we have a list of 12 files on 2009
        one for each month and we provide months=['January', 'February'] the filter will return 2 urls.

        params:
            - urls: array of ITS_LIVE urls
            - max_files_per_year: int, max number of files per year even if they fall into the correct months
            - months: array of named months of the year, i.e. ['January', 'December']
        returns:
            - if by_year is true returns a dictionary with years as keys and ITS_LIVE urls as values for each year
              if by_year is false, returns a flat list of urls that satisfy the filter parameters
        """
        # LE07_L1TP_008012_20030417_20170125_01_T1_X_LE07_L1TP_008012_20030401_20170126_01_T1_G0240V01_P095.nc
        if urls is None:
            return None
        filtered_urls = []
        year_counts = {}

        for url in urls:
            coverage = self._get_temporal_coverage(url)
            if months is not None and len(months) > 0:
                if coverage['mid_date'].strftime("%B") in months or coverage['mid_date'].strftime("%b") in months:
                    if str(coverage['mid_date'].year) not in year_counts:
                        year_counts[str(coverage['mid_date'].year)] = [url]
                        filtered_urls.append(url)
                    else:
                        if len(year_counts[str(coverage['mid_date'].year)]) < max_files_per_year:
                            filtered_urls.append(url)
                            year_counts[str(coverage['mid_date'].year)].append(url)
                        else:
                            continue
            else:
                if str(coverage['mid_date'].year) not in year_counts:
                        year_counts[str(coverage['mid_date'].year)] = [url]
                        filtered_urls.append(url)
                else:
                    if len(year_counts[str(coverage['mid_date'].year)]) < max_files_per_year:
                        filtered_urls.append(url)
                        year_counts[str(coverage['mid_date'].year)].append(url)
                    else:
                        continue
        self.filtered_urls = filtered_urls
        self.filtered_urls_by_year = dict(sorted(year_counts.items()))

        if by_year:
            return self.filtered_urls_by_year
        else:
            return self.filtered_urls


    def build_query_params(self, params=None):
        """
        returns a query string for the ITS_LIVE API that can be used on the /coverages or the /urls endpoints.
        for information about the endpooint see the documentation:
        https://nsidc.org/apps/itslive-search/docs#/

        params:
            -params: dict, if empty, this method will try to use the current widget state to build the query string
            if dict is passed it should have the following keys:
            {
                'polygon': [1,2,3,4,5,1,2],
                'start': '2000-01-01',
                'end': '2009-01-01',
                'percent_valid_pixels': 10,
                'min_interval': 7,
                'max_interval': 120
            }
        """
        if params is None:
            params = self.get_current_selection()
            if params['min_interval'] == 'any':
                min_interval = ''
            else:
                min_interval = f"&min_interval={params['min_interval']}"
            if params['max_interval'] == 'any':
                max_interval = ''
            else:
                max_interval = f"&max_interval={params['max_interval']}"
            points = ','.join(f'{p[0]},{p[1]}' for p in params['geometry']['coordinates'][0])
            url = f"""
            polygon={points}&
            start={params['start']}&
            end={params['end']}&
            percent_valid_pixels={params['percent_valid_pixels']}
            {min_interval}
            {max_interval}
            """.replace('\n', '').replace('  ', '')
        else:
            if polygon in params:
                geometry_query = f"polygon={params['polygon']}&"
            else:
                geometry_query = f"bbox={params['bbox']}&"
            url = f"""
            {geometry_query}
            start={params['start']}&
            end={params['end']}&
            percent_valid_pixels={params['percent_valid_pixels']}&
            min_interval={params['min_separation']}&
            max_interval={params['max_separation']}&
            mission={params['mission']}&
            serialization={params['serialization']}
            """.replace('\n', '').replace('  ', '')
        return url


    def display(self, projection='global'):
        """
        displays the map widget
        """
        if hasattr(self, 'map'):
            self._set_state()
        self._create_controls()
        self._create_map(projection)
        self._bind_widgets()
        self._out.clear_output()
        if self.properties['geometry'] is not None:
            self.map.add_layer(self.properties['geometry'])
        if self.properties['orientation'] == 'vertical':
            if hasattr(self, '_sc'):
                self._sc.clear_output()
            else:
                self._sc = Sidecar(title='Map Widget')
            with self._sc:
                display(self._out)
            with self._out:
                display(self.map)
                for component in self.controls:
                    display(component)
                fig = self._draw_counts()
                if fig is not None:
                    display(fig)

        else:
            with self._out:
                display(self.map)
                for component in self.controls:
                    display(component)
                fig = self._draw_counts()
                if fig is not None:
                    display(fig)
            display(self._out)

    def get_current_selection(self):
        """
        returns the current geometry selection as a geojson object.
        """
        if self.properties['geometry'] is None:
            print('No area selected, need to draw a polygon or bbox first')
            return None
        params = {
            'geometry': self.properties['geometry'].data['geometry'],
            'min_interval': self._control_min_separation.value,
            'max_interval': self._control_max_separation.value,
            'percent_valid_pixels': self._control_coverage.value,
            'start': self._control_dates_range.value[0].date().strftime('%Y-%m-%d'),
            'end': self._control_dates_range.value[1].date().strftime('%Y-%m-%d')
        }
        return params


    def download_file(self, url, directory, file_paths):
        local_filename = url.split('/')[-1]
        # NOTE the stream=True parameter below
        if not os.path.exists(f'{directory}/{local_filename}'):
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(f'{directory}/{local_filename}', 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                file_paths.append(local_filename)
        return local_filename

    def add_layer(self, props, **kwargs):
        return None

    def download_velocity_granules(self, urls, path_prefix=None, params=None, start=0, end=-1, threads=8):
        """
        downloads a list of URLS into the data directory.
        and dumps the current parameters to help identify the files later on.
        params:
            - urls: array of ITS_LIVE urls
            - path_prefix: directory on which the files will be downloaded.
            - start: int, start index offset.
            - end: int, end index offset
        returns:
           - array: list of the downloaded files
        """
        if self.properties['geometry'] is None and params is None:
            print("Files will be download but the parameters won't be included")
            params = {'Params':'Not provided'}
        elif params is None:
            params = self.get_current_selection()

        if path_prefix is None:
            directory_prefix = f"data/{datetime.today().strftime('%Y-%m-%d')}-{uuid4().hex[:6]}"
        else:
            directory_prefix = path_prefix
        if not os.path.exists(directory_prefix):
            os.makedirs(directory_prefix)

        with open(f'{directory_prefix}/params.json', 'w+') as outfile:
            outfile.write(json.dumps(params))
        if urls is None:
            return None
        if start < 0:
            start = 0
        if end >= len(urls) or end == -1:
            end = len(urls)
        file_paths = []
        arguments = [(url, directory_prefix, file_paths) for url in urls[start:end]]
        result = pqdm(arguments, self.download_file, n_jobs=threads, argument_type='args')

        return file_paths
