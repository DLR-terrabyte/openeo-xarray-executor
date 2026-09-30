import logging
import uuid

import numpy as np
import os
import pyproj
import pystac_client
import xarray as xr

from odc.stac import stac_load
from pathlib import Path
from pystac.extensions import raster
from typing import Optional, Union
from openeo_processes_dask.process_implementations.data_model import (
    RasterCube
)
from openeo_processes_dask.process_implementations.cubes._filter import filter_bbox
from openeo_pg_parser_networkx.pg_schema import BoundingBox, GeoJson, TemporalInterval

__all__ = ["load_collection", "save_result"]

logger = logging.getLogger(__name__)

_PACKAGE_SAVE_RESULT_FORMATS = {"GTIFF", "COG", "NETCDF", "ZARR"}

def load_collection(
    id: str,
    spatial_extent: Optional[Union[BoundingBox, dict, str, GeoJson]] = None,
    temporal_extent: Optional[TemporalInterval] = None,
    bands: Optional[list[str]] = None,
    properties: Optional[dict] = None,
    **kwargs,
):
    logging.info("load_collection")
    query_dict = {}

    query_dict["collections"] = [id]

    if spatial_extent is None:
        raise Exception(
            "No spatial extent was provided, will not load the entire x and y axis of the datacube."
        )
    elif temporal_extent is None:
        raise Exception(
            "No temporal extent was provided, will not load the entire temporal axis of the datacube."
        )

    if isinstance(spatial_extent, BoundingBox):
        query_dict["bbox"] = (
            spatial_extent.west,
            spatial_extent.south,
            spatial_extent.east,
            spatial_extent.north,
        )
    else:
        raise ValueError("Provided spatial extent could not be interpreted.")

    #query_dict["datetime"] = tuple(
    #    [str(time.root) for time in temporal_extent if time != 'None']
    #)

    query_dict["datetime"] = tuple(
        [time.root.isoformat() for time in temporal_extent if time != "None"]
    )

    if "STAC_API_URL" not in os.environ:
        raise Exception("STAC URL Not available in executor config.")

    logging.info("STAC_API_URL: " + os.environ["STAC_API_URL"])
    catalog = pystac_client.Client.open(os.environ["STAC_API_URL"])
    results = catalog.search(**query_dict, limit=10)

    result_items = list(results.items())
    logging.info("found %s items" % len(result_items))

    example_item = result_items[0]

    print("Properties keys:", list(example_item.properties.keys()))
    print("proj:epsg:", example_item.properties.get("proj:epsg"))
    print("to_dict proj:epsg:", example_item.to_dict()["properties"].get("proj:epsg"))
    print("proj:code:", example_item.properties.get("proj:code"))
    print("to_dict proj:code:", example_item.to_dict()["properties"].get("proj:code"))

    if "proj:wkt2" in example_item.properties.keys():
        crs = pyproj.CRS.from_wkt(example_item.properties["proj:wkt2"])
    elif "proj:code" in example_item.properties.keys():
        crs = pyproj.CRS.from_user_input(example_item.properties["proj:code"])
    elif "proj:epsg" in example_item.properties.keys():
        crs = pyproj.CRS.from_epsg(example_item.properties["proj:epsg"])
    else:
        raise ValueError("Error: No CRS detected in properties.")


    if raster.RasterExtension.has_extension(example_item):
        for asset in example_item.get_assets().values():
            if 'raster:bands' in asset.extra_fields.keys():
                for band in asset.extra_fields['raster:bands']:
                    if 'spatial_resolution' in band:
                        resolution = band['spatial_resolution']
                    if 'nodata' in band:
                        nodata = band['nodata']
                    if 'data_type' in band:
                        dtype = band['data_type']
            if resolution and nodata and dtype:
                break
    else:
        crs_measurement = pyproj.CRS.from_wkt(crs).axis_info[0].unit_name

        if crs_measurement == 'metre':
            resolution = 10
        elif crs_measurement == 'degree':
            resolution = 0.0009
        
    # TODO Need to tidy up the logic above.
    kwargs = {}
    # TODO Need to ensure nodata belongs to the dtype
    if dtype:
        kwargs["dtype"] = dtype

        if "int" in dtype and isinstance(nodata, float):
            nodata = int(nodata)

    if nodata:
        kwargs["nodata"] = nodata       

    lazy_xarray = stac_load(
        result_items,
        crs=crs,
        resolution=resolution,
        # TODO Add some way to decide chunks
        chunks={"x": 2048, "y": 2048},
        **kwargs
    ).to_array(dim='bands')
    logging.info(lazy_xarray)

    # Add some sort of clipping here to the original bounding box that was requested.
    return filter_bbox(lazy_xarray, extent=spatial_extent)


def save_result(
    data: RasterCube,
    format: str = "netcdf",
    options: Optional[dict] = None,
):
    """Save the result data cube to a file."""
    options = dict(options or {})
    fmt_upper = format.upper()

    use_package_writer = options.pop("use_package_save_result", False)
    if fmt_upper in _PACKAGE_SAVE_RESULT_FORMATS or use_package_writer:
        return _save_result_with_process_package(data, fmt_upper, options)

    supported = ", ".join(sorted(_PACKAGE_SAVE_RESULT_FORMATS))
    raise ValueError(
        f"Data can't be transformed into the requested output format '{format}'. "
        f"Supported formats: {supported}"
    )


def _save_result_with_process_package(
    data: RasterCube,
    fmt_upper: str,
    options: dict,
) -> str:
    """Delegate richer output formats to openeo-processes-save-result.

    The standalone process returns STAC metadata. In argoworkflows, downstream
    EOAP-CWL staging expects a local path, so this wrapper returns the first
    local asset path referenced by that STAC output, falling back to the
    collection JSON or output folder.
    """
    try:
        from openeo_processes_save_result.save_result import (
            save_result as package_save_result,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Output format "
            f"'{fmt_upper}' requires openeo-processes-save-result to be installed "
            "in the executor image."
        ) from exc

    results_path = Path(os.environ.get("OPENEO_RESULTS_PATH", "/tmp/results"))
    results_path.mkdir(parents=True, exist_ok=True)
    output_folder = Path(
        options.setdefault("output_folder", str(results_path / str(uuid.uuid4())))
    )
    collection_id = options.get("collection_id", "save_result")

    cube = _as_dataset_for_save_result_package(data)

    # Executor pods run in air-gapped environments where PySTAC cannot fetch
    # remote STAC extension schemas (stac-extensions.github.io). Disable
    # validation to prevent GetSchemaError in offline mode.
    options = dict(options)
    options.setdefault("skip_validation", True)

    stac = package_save_result(data=cube, format=fmt_upper, options=options)

    # staged_path = _local_asset_path_from_stac(stac, output_folder)
    # if staged_path is not None:
    #     logger.info(
    #         "Successfully saved result via openeo-processes-save-result: %s",
    #         staged_path,
    #     )
    #     return str(staged_path)
    #
    # if fmt_upper == "ZARR" and output_folder.exists():
    #     return str(output_folder)
    #
    # collection_json = output_folder / f"{collection_id}.json"
    # if collection_json.exists():
    #     return str(collection_json)

    return str(output_folder)


def _as_dataset_for_save_result_package(data: RasterCube) -> xr.Dataset:
    if isinstance(data, xr.Dataset):
        return data

    dim = data.openeo.band_dims[0] if data.openeo.band_dims else None
    return data.to_dataset(
        dim=dim, name="name" if not dim else None, promote_attrs=True
    )

#
# def _local_asset_path_from_stac(stac: dict, output_folder: Path) -> Optional[Path]:
#     asset_refs = []
#
#     if stac.get("type") == "Feature":
#         asset_refs.extend(
#             (asset.get("href"), output_folder)
#             for asset in stac.get("assets", {}).values()
#         )
#
#     for link in stac.get("links", []):
#         if link.get("rel") != "item":
#             continue
#         href = link.get("href")
#         if not href:
#             continue
#         item_path = _resolve_local_href(href, output_folder)
#         if item_path is None or not item_path.exists() or item_path.suffix != ".json":
#             continue
#         try:
#             import json
#
#             with open(item_path) as f:
#                 item = json.load(f)
#         except Exception as exc:
#             logger.warning("Could not read STAC item %s: %s", item_path, exc)
#             continue
#         asset_refs.extend(
#             (asset.get("href"), item_path.parent)
#             for asset in item.get("assets", {}).values()
#         )
#
#     items_dir = output_folder / "items"
#     if items_dir.exists():
#         for item_path in sorted(items_dir.glob("*.json")):
#             try:
#                 import json
#
#                 with open(item_path) as f:
#                     item = json.load(f)
#             except Exception as exc:
#                 logger.warning("Could not read STAC item %s: %s", item_path, exc)
#                 continue
#             asset_refs.extend(
#                 (asset.get("href"), item_path.parent)
#                 for asset in item.get("assets", {}).values()
#             )
#
#     for href, base in asset_refs:
#         path = _resolve_local_href(href, base)
#         if path is not None and path.exists():
#             return path
#
#     return None
#
#
# def _resolve_local_href(href: Optional[str], base: Path) -> Optional[Path]:
#     if not href or "://" in href:
#         return None
#
#     path = Path(href)
#     if not path.is_absolute():
#         path = base / href.lstrip("./")
#     return path
