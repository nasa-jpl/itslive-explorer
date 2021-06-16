from ipyleaflet import projections, basemaps, TileLayer

north_3413 = {
    'name': 'EPSG:3413',
    'custom': True,
    'proj4def': '+proj=stere +lat_0=90 +lat_ts=70 +lon_0=-45 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs',
    'origin': [-4194304, 4194304],
    'bounds': [
        [-4194304, -4194304],
        [4194304, 4194304]
    ],
    'resolutions': [
        16384.0,
        8192.0,
        4096.0,
        2048.0,
        1024.0,
        512.0,
        256.0
    ]
}

south_3031 = {
    'name': 'EPSG:3031',
    'custom': True,
    'proj4def': '+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs',
    'origin': [-4194304, 4194304],
    'bounds': [
        [-4194304, -4194304],
        [4194304, 4194304]
    ],
    'resolutions': [
        16384.0,
        8192.0,
        4096.0,
        2048.0,
        1024.0,
        512.0,
        256.0
    ]
}

projections = {
    'global': {
        'base_map': basemaps.NASAGIBS.BlueMarble,
        'projection': projections.EPSG3857,
        'center': (0, 0),
        'zoom': 1,
        'max_zoom': 8,
        'layers': [
            TileLayer(
                url="http://personal-temporary-share.s3-website-us-west-1.amazonaws.com/ITS_LIVE_velOnly_itslive_4326_cog_zyx/{z}/{y}/{x}.png",
                name="ITS_LIVE velocity mosaic",
                tms=False,
                tile_size=512,
                opacity=0.6
            )
        ]

    },
    'north': {
        'base_map': basemaps.NASAGIBS.BlueMarble3413,
        'projection': north_3413,
        'center': (90, 0),
        'zoom': 1,
        'max_zoom': 4,
        'layers': [
            TileLayer(
                url="http://personal-temporary-share.s3-website-us-west-1.amazonaws.com/ITS_LIVE_velOnly_itslive_3413_cog_zyx/{z}/{y}/{x}.png",
                name="ITS_LIVE velocity mosaic",
                tms=False,
                tile_size=512,
                opacity=0.6
            ),
            TileLayer(
                url="https://gibs.earthdata.nasa.gov/wmts/epsg3413/best/Coastlines/default/250m/{z}/{y}/{x}.png",
                name="Coastlines",
                tms=True,
                opacity=1.0
            )
        ]

    },
    'south': {
        'base_map': basemaps.NASAGIBS.BlueMarble3031,
        'projection': south_3031,
        'center': (-90, 0),
        'zoom': 1,
        'max_zoom': 4,
        'layers': [
            TileLayer(
                url="http://personal-temporary-share.s3-website-us-west-1.amazonaws.com/ITS_LIVE_velOnly_itslive_3031_cog_zyx/{z}/{y}/{x}.png",
                name="ITS_LIVE velocity mosaic",
                tms=False,
                tile_size=512,
                opacity=0.6
            ),
            TileLayer(
                url="https://gibs.earthdata.nasa.gov/wmts/epsg3031/best/Coastlines/default/250m/{z}/{y}/{x}.png",
                name="Coastlines",
                opacity=1.0,
                tms=True
            )
        ]

    }
}



