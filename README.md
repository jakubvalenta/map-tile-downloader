# Map Tile Downloader

Command line script to download PNG [map
tiles](https://en.wikipedia.org/wiki/Tiled_web_map) from a web map. It takes
geographic coordinates and a zoom level as its input.

This project is an example of how you could achieve such a task. It
intentionally doesn't download in parallel. If you use it with a real map
service, be nice.

Quick example:

```shell
uv run map-tile-downloader 'https://content-a.strava.com/identified/globalheat/all/hot/$z/$x/$y.png?v=19&t=$timestamp&missing=empty' 50.0598,14.4656 --zoom=10 --output-dir=tiles --referer 'https://www.strava.com'
```

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)

## Usage

### URL template

First figure out the URL template of your web map service. You can use variables
`$x`, `$y`, `$z`, `$timestamp`. Example:

```
https://content-a.strava.com/identified/globalheat/all/hot/$z/$x/$y.png?v=19&t=$timestamp&missing=empty
```

### Cookies

If your web map needs cookies, copy them from your web browser (like Firefox) to
the file **cookies.env**. Example:

```
'_strava4_session'=XXX
'_strava_idcf'=XXX
'_strava_CloudFront-Expires'=XXX
'CloudFront-Key-Pair-Id'=XXX
'CloudFront-Policy'=XXX
'CloudFront-Signature'=XXX
```

### Download

Once you have your [URL template](#url-template) and [cookies](#cookies), you
can run the download script.

Download a **single tile** for given point at given zoom level:

```shell
uv run map-tile-downloader 'https://content-a.strava.com/identified/globalheat/all/hot/$z/$x/$y.png?v=19&t=$timestamp&missing=empty' 50.0598,14.4656 --zoom=10 --output-dir=tiles --referer 'https://www.strava.com'
```

Download **all tiles** within a rectangle defined by two points at given zoom level:

```shell
uv run map-tile-downloader 'https://content-a.strava.com/identified/globalheat/all/hot/$z/$x/$y.png?v=19&t=$timestamp&missing=empty' 50.0598,14.4656 50.023234,14.528893 --zoom=10 --output-dir=tiles --referer 'https://www.strava.com'
```

Download **all tiles and their ancestor tiles** (tiles at lower zoom levels):

```shell
uv run map-tile-downloader 'https://content-a.strava.com/identified/globalheat/all/hot/$z/$x/$y.png?v=19&t=$timestamp&missing=empty' 50.0598,14.4656 50.023234,14.528893 --zoom=10 --ancestors --output-dir=tiles --referer 'https://www.strava.com'
```

You will find the downloaded PNG files in the directory `tiles`. You can use
[Raster Tile Server](https://github.com/jakubvalenta/raster-tile-server) to
preview the map.

### Help

See all available command line options:

```shell
uv run map-tile-downloader -h
```

## License

This project is marked [CC0
1.0](https://creativecommons.org/publicdomain/zero/1.0/).
