import osmnx as ox
import geopandas as gpd
from shapely.geometry import Point
from shapely import union_all
from shapely.ops import nearest_points
from pyproj import Transformer
import math
import ee
import io
import streamlit as st
import pandas as pd
import streamlit as st
import ee
from google.oauth2 import service_account

def initialize_ee():
    try:
        # Check if Earth Engine is already initialized
        ee.data.getAlgorithms()
    except Exception:
        service_account_info = dict(st.secrets["gcp_service_account"])
        
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/earthengine']
        )
        
        ee.Initialize(
            credentials=credentials, 
            project=service_account_info["project_id"]
        )

# Initialize using your verified Project ID

def eval_en_av(shapely_point):

    lon = shapely_point.x
    lat = shapely_point.y

    """
    Samples nighttime light radiance from the NOAA VIIRS dataset in GEE.
    Categorizes the location's proximity/reliability to an active energy grid.
    """
    # 2. Define the Point Geometry
    point = ee.Geometry.Point([lon, lat])
    
    # 3. Load the VIIRS Nighttime Lights Monthly Composite
    # We filter for a recent stable period to get a clean operational baseline
    viirs_collection = (ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
                        .filterDate('2025-01-01', '2025-12-31')
                        .select('avg_rad')) # avg_rad = Average Radiance
    
    # Reduce the collection to a single median image to wipe out temporary anomalies (flares, boats)
    stable_lights = viirs_collection.median()
    
    # 4. Sample the pixel value
    # scale=464 matches the native resolution of VIIRS (~15 arc-seconds)
    sampled_data = stable_lights.sample(point, scale=464).first().getInfo()
    
    # Handle missing data or open ocean
    if not sampled_data or 'properties' not in sampled_data or not sampled_data['properties']:
        return {
            "radiance_value": 0.0,
            "energy_grid_status": "Off-Grid / Isolated"
        }
        
    # Extract raw radiance value (nanoWatts / cm2 / sr)
    radiance = list(sampled_data['properties'].values())[0]
    
    # 5. Evaluate status using clear infrastructure thresholds
    if radiance >= 5.0:
        # High radiance: Dense urban or stable commercial grid connection
        status = "Stable_Grid_Connected" 
    elif 0.5 <= radiance < 5.0:
        # Low/Moderate radiance: Rural settlement, peri-urban, or intermittent grid access
        status = "Unstable_Or_Peripheral_Grid"
    else:
        # Near-zero radiance: Completely unlit, deep rural, or wilderness
        status = "Off_Grid"
        
    return {
        "radiance_value": round(radiance, 2),
        "energy_grid_status": status
    }


def dist_road(shapely_point, buffer_meters=5000):
    """
    Safely calculates the closest distance in meters from a point to the nearest 
    drivable road without generating library deprecation warnings.
    """
    lon = shapely_point.x
    lat = shapely_point.y
    
    try:
        # 1. Download the unprojected graph directly in Lat/Lon
        graph = ox.graph_from_point((lat, lon), dist=buffer_meters, network_type='drive')
        
        # 2. Extract edge geometries
        _, edges_gdf = ox.graph_to_gdfs(graph, nodes=True, edges=True)
        
        # FIX 1: Use union_all() instead of the deprecated .unary_union attribute
        all_roads = union_all(edges_gdf.geometry)
        
        # 3. Find the closest point on the road network
        nearest_geom_point, _ = nearest_points(all_roads, shapely_point)
        
        # FIX 2: Use modern PyProj Transformer instead of the deprecated pyproj.transform
        # Auto-detects the best local metric projection zone based on your coordinates
        # (Using EPSG:3857 Web Mercator for clean, global metric distance measurements)
        transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
        
        # Unpack and transform points cleanly
        x1, y1 = transformer.transform(shapely_point.x, shapely_point.y)
        x2, y2 = transformer.transform(nearest_geom_point.x, nearest_geom_point.y)
        
        # Create temporary metric points to run standard distance math
        point_transformed = Point(x1, y1)
        road_transformed = Point(x2, y2)
        
        distance_meters = point_transformed.distance(road_transformed)
        
        return round(distance_meters, 2)

    except Exception as e:
        print(f"Road network query update: {e}")
        return buffer_meters

def dist__river(shapely_point):

    lon = shapely_point.x
    lat = shapely_point.y
    """
    Uses native Google Earth Engine FeatureCollection distance calculations
    to find the exact distance (in meters) to the nearest river stream.
    """
    # 1. Define the pinpoint geometry
    point = ee.Geometry.Point([lon, lat])
    
    # 2. Load the global continuous river vector layer
    rivers = ee.FeatureCollection('WWF/HydroSHEDS/v1/FreeFlowingRivers')
    
    # 3. FIX: Compute distance directly from the FeatureCollection.
    # searchRadius is measured in meters (100,000 meters = 100 km limit)
    # maxError is the allowable projection tolerance in meters
    distance_image = rivers.distance(searchRadius=100000, maxError=100)
    
    # 4. Extract the pixel value at the designated coordinate location
    sample = distance_image.sample(point, scale=30)
    
    # 5. Parse and safely convert the result back into Python
    try:
        pixel_data = sample.first().getInfo()
        # The output band generated by feature collection distance is named 'distance'
        distance_meters = pixel_data['properties']['distance']
        return float(round(distance_meters,2))
    except Exception as e:
        # If no river is found within the 100 km radius, return the maximum boundary threshold
        return 100000.0


def urban_road_den(shapely_point, radius_meters=3000, tier3_threshold_km_km2=25.0):
    """
    Downloads nearby roads, projects the network to accurately calculate length densities,
    and determines if an area is urban based strictly on Tier 3 (Local) road density.
    """
    lon = shapely_point.x
    lat = shapely_point.y
    
    try:
        # 1. Fetch the entire drivable network around the coordinate
        graph = ox.graph_from_point((lat, lon), dist=radius_meters, network_type='drive')
        
        # FIX 1: Project graph to local UTM (meters) so length metrics and area align perfectly
        graph_projected = ox.project_graph(graph)
    except Exception as e:
        return {"tier_3_density_km_km2": 0.0, "is_urban": 0}
        
    # Convert projected graph edges to a standard GeoDataFrame
    _, edges = ox.graph_to_gdfs(graph_projected)
    
    if 'highway' not in edges.columns:
        return {"tier_3_density_km_km2": 0.0, "is_urban": 0}
    
    # Handle list-based tags
    edges['highway_clean'] = edges['highway'].apply(lambda x: x[0] if isinstance(x, list) else x)
    
    # Tier 3: Local Access Infrastructure (Residential, living streets, etc.)
    tier_3_tags = ['tertiary', 'unclassified', 'residential', 'tertiary_link', 'living_street', 'service']
    tier_3_len_meters = edges[edges['highway_clean'].isin(tier_3_tags)]['length'].sum()
    
    # Convert total meters to kilometers
    tier_3_len_km = tier_3_len_meters / 1000.0
    
    # Calculate buffer area in square kilometers (km2)
    radius_km = radius_meters / 1000.0
    buffer_area_km2 = math.pi * (radius_km ** 2)
    
    # Calculate density: km of local road per km2 of land area
    tier_3_density = round(float(tier_3_len_km / buffer_area_km2), 2)
    
    # 2. Evaluate Binary Matrix Signal (1 for Urban, 0 for Rural/Peripheral)
    is_urban_signal = 1 if tier_3_density >= tier3_threshold_km_km2 else 0
    
    return {
        "tier_3_density_km_km2": tier_3_density,
        "is_urban": is_urban_signal
    }

def dist_sew(shapely_point, max_search_radius_meters=20000):
    
    lon = shapely_point.x
    lat = shapely_point.y
    
    """
    Finds the absolute minimum distance in meters to the nearest centralized 
    sewer line, wastewater pipeline, or treatment facility using global OSM tags.
    """
    origin_point = Point(lon, lat)
    
    # Universal OSM tags for sanitation systems. 
    # Setting sub-keys to True catches ALL assets under that main category.
    sewer_tags = {
        'man_made': ['pipeline', 'wastewater_plant', 'works', 'sewer'],
        'substance': 'wastewater',
        'utility': 'sewer',
        'industrial': ['wastewater', 'sewage_works', 'sewage']
    }
    
    try:
        # FIX: Updated to the modern 'features_from_point' function
        sewer_features = ox.features_from_point((lat, lon), dist=max_search_radius_meters, tags=sewer_tags)
    except Exception as e:
        # Let's print out the real reason if the API fails or times out
        print(f"OSMnx Query Notice: {e}")
        return float(max_search_radius_meters)
        
    if sewer_features.empty:
        print("Notice: No mapped sewage assets found within the search radius.")
        return float(max_search_radius_meters)
        
    # Project data to local UTM coordinates for accurate meter distance tracking
    origin_gdf = gpd.GeoDataFrame(geometry=[origin_point], crs="EPSG:4326")
    origin_projected = ox.projection.project_gdf(origin_gdf)
    sewer_projected = ox.projection.project_gdf(sewer_features)
    
    projected_point = origin_projected.geometry.iloc[0]
    
    # Calculate shortest physical distance from user point to any sewer asset component
    distances = sewer_projected.distance(projected_point)
    min_distance_meters = distances.min()
    
    return float(round(min_distance_meters,2))

def dist_supply(shapely_point):
    
    lon = shapely_point.x
    lat = shapely_point.y
    
    """
    Finds the distance to the nearest water supply asset using an optimized,
    tiered search radius to prevent Overpass API slowdowns.
    """
    origin_point = Point(lon, lat)
    
    # Universal OSM tags for clean water/supply infrastructure
    supply_tags = {
        'utility': ['water', 'water_distribution'],
        'man_made': ['water_works', 'water_tower', 'pumping_station', 'reservoir_covered'],
        'amenity': ['water_point', 'drinking_water']
    }
    
    # Tiered search radii (in meters): checks 2km, then 5km, then 10km if needed
    search_radii = [2000, 5000, 10000]
    
    supply_features = None
    chosen_radius = search_radii[-1] # Fallback ceiling
    
    for radius in search_radii:
        try:
            # Query a smaller bounding area first
            supply_features = ox.features_from_point((lat, lon), dist=radius, tags=supply_tags)
            
            # If we found elements, break early to save time and memory!
            if not supply_features.empty:
                chosen_radius = radius
                break
        except Exception:
            # If the radius is empty, OSMnx throws an exception; we just move to the next tier
            continue

    # Fallback if absolutely nothing was found across any tier
    if supply_features is None or supply_features.empty:
        print(f"Notice: No water supply features found within {chosen_radius/1000} km.")
        return float(chosen_radius)
        
    # Project data to local UTM coordinates for accurate meter measurements
    origin_gdf = gpd.GeoDataFrame(geometry=[origin_point], crs="EPSG:4326")
    origin_projected = ox.projection.project_gdf(origin_gdf)
    supply_projected = ox.projection.project_gdf(supply_features)
    
    projected_point = origin_projected.geometry.iloc[0]
    
    # Calculate shortest physical distance to any asset component
    distances = supply_projected.distance(projected_point)
    min_distance_meters = distances.min()
    
    return float(round(min_distance_meters,2))

def extract_macro_climate(shapely_point):
    
    lon = shapely_point.x
    lat = shapely_point.y

    """
    Extracts the Köppen-Geiger climate class from a global raster in GEE 
    and simplifies it into an operational macro-environmental profile using ranges.
    """
    # 2. Define the Point Geometry
    point = ee.Geometry.Point([lon, lat])
    
    # 3. Load the Global Köppen-Geiger Raster
    kg_image = ee.Image("users/fsn1995/Global_19862010_KG_5m")
    
    # 4. Sample the pixel value at our coordinate point
    sampled_data = kg_image.sample(point, scale=9277).first().getInfo()
    
    # Handle cases where coordinates fall on open ocean or missing data
    if not sampled_data or 'properties' not in sampled_data or not sampled_data['properties']:
        return "Unknown / Water Body"
        
    # Extract the raw integer value
    raw_kg_id = list(sampled_data['properties'].values())[0]
    
    # 5. Evaluate the macro profile using defined range limits
    if 1 <= raw_kg_id <= 4:
        resolved_profile = "Tropical_Warm"     # Main Class A
    elif 5 <= raw_kg_id <= 8:
        resolved_profile = "Arid_SemiArid"     # Main Class B
    elif 9 <= raw_kg_id <= 31:
        resolved_profile = "Temperate_Cold"    # Main Classes C, D, E
    else:
        resolved_profile = "Unknown / Out of Bounds"
    
    return {
        "latitude": lat,
        "longitude": lon,
        "raw_koppen_id": raw_kg_id,
        "macro_environmental_zone": resolved_profile
    }

def extract_macro_economics(shapely_point):

    lon = shapely_point.x
    lat = shapely_point.y

    """
    Queries the official USDOS LSIB dataset in GEE to find the country,
    then assigns a macro-economic tier using a clean country-level profile.
    """
    # 2. Define the Point Geometry
    point = ee.Geometry.Point([lon, lat])
    
    # 3. Load the Official GEE International Boundary Dataset
    countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
    
    # 4. Filter the collection to find which country polygon contains our point
    matching_country = countries.filterBounds(point).first()
    
    # Extract properties from the cloud
    country_info = matching_country.getInfo()
    
    # Handle open ocean or points outside recognized land boundaries
    if not country_info or 'properties' not in country_info:
        return {
            "country_name": "Unknown / International Waters",
            "macro_economic_tier": "Low_Income" # Conservative default for safety
        }
        
    country_name = country_info['properties']['country_na']
    
    # 5. Global Economic Profiles (World Bank Income Level Mapping)
    # Add or modify countries here based on your paper's framework
    high_income_countries = [
        "United States", "Canada", "Germany", "United Kingdom", "France", "Japan", 
        "South Korea", "Australia", "Spain", "Italy", "Chile", "Uruguay", "Panama"
    ]
    
    low_income_countries = [
        "Afghanistan", "Ethiopia", "Madagascar", "Mali", "Sudan", "Yemen", 
        "Haiti", "Niger", "Somalia", "Democratic Republic of the Congo"
    ]
    
    # 6. Evaluate the macro-economic tier using standard membership checks
    if country_name in high_income_countries:
        resolved_tier = 1 #High_income
    elif country_name in low_income_countries:
        resolved_tier = 3 #Low_Income
    else:
        resolved_tier = 2 # Defaults cleanly to Middle-Income (e.g., Colombia, Brazil, Mexico)

    return {
        "country_name": country_name,
        "macro_economic_tier": resolved_tier
    }

def dist_pgrid(shapely_point, buffer_meters=5000):
    """
    Queries OpenStreetMap for physical power infrastructure using modern OSMnx v2.0+ 
    syntax and calculates the distance to the nearest asset in meters.
    """
    lon = shapely_point.x
    lat = shapely_point.y
    
    power_tags = {
        'power': ['line', 'minor_line', 'cable', 'substation', 'transformer']
    }
    
    try:
        # 1. FIX: Use modern features_from_point with a center_point tuple
        center_point = (lat, lon)
        power_gdf = ox.features_from_point(center_point, tags=power_tags, dist=buffer_meters)
        
        if power_gdf.empty:
            print(f"No power grid infrastructure found within a {buffer_meters}m radius.")
            return buffer_meters
            
        # 2. Combine geometries
        all_power_infrastructure = union_all(power_gdf.geometry)
        
        # 3. Find the closest point
        nearest_grid_point, _ = nearest_points(all_power_infrastructure, shapely_point)
        
        # 4. Transform to metric tracking
        transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
        x1, y1 = transformer.transform(shapely_point.x, shapely_point.y)
        x2, y2 = transformer.transform(nearest_grid_point.x, nearest_grid_point.y)
        
        point_transformed = Point(x1, y1)
        grid_transformed = Point(x2, y2)
        
        return round(point_transformed.distance(grid_transformed), 2)

    except Exception as e:
        print(f"Power grid infrastructure query status: {e}")
        return buffer_meters

def dist_ptar(shapely_point, buffer_meters=10000):
    """
    Queries OpenStreetMap for centralized wastewater treatment plants (PTAR)
    within a designated search radius and calculates the distance in meters.
    """
    lon = shapely_point.x
    lat = shapely_point.y
    
    # Define comprehensive OSM tags for wastewater treatment facilities
    ptar_tags = {
        'utility': ['wastewater_plant', 'sewerage_works'],
        'man_made': ['wastewater_works', 'water_works']
    }
    
    try:
        # 1. Query infrastructure features around the center point tuple
        center_point = (lat, lon)
        ptar_gdf = ox.features_from_point(center_point, tags=ptar_tags, dist=buffer_meters)
        
        if ptar_gdf.empty:
            print(f"No existing PTAR infrastructure found within a {buffer_meters}m radius.")
            return buffer_meters
            
        # 2. Combine geometries (PTARs are often mapped as large polygons or points)
        all_ptar_infrastructure = union_all(ptar_gdf.geometry)
        
        # 3. Calculate the closest point on the infrastructure map
        nearest_ptar_point, _ = nearest_points(all_ptar_infrastructure, shapely_point)
        
        # 4. Transform to metric coordinate reference system (EPSG:3857)
        transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
        x1, y1 = transformer.transform(shapely_point.x, shapely_point.y)
        x2, y2 = transformer.transform(nearest_ptar_point.x, nearest_ptar_point.y)
        
        point_transformed = Point(x1, y1)
        ptar_transformed = Point(x2, y2)
        
        return round(point_transformed.distance(ptar_transformed), 2)

    except Exception as e:
        print(f"PTAR infrastructure query status: {e}")
        return buffer_meters
    
def dist_green_area(shapely_point, buffer_meters=5000):
    """
    Queries OpenStreetMap for green areas (parks, nature reserves, forests)
    around a coordinate and calculates the distance to the nearest asset in meters.
    """
    lon = shapely_point.x
    lat = shapely_point.y
    
    # Define tags that target environmental and recreational green spaces
    green_tags = {
        'leisure': ['park', 'nature_reserve', 'common'],
        'landuse': ['forest', 'meadow', 'orchard', 'grass'],
        'natural': ['wood', 'valley', 'wetland']
    }
    
    try:
        # 1. Query green features around the center point tuple
        center_point = (lat, lon)
        green_gdf = ox.features_from_point(center_point, tags=green_tags, dist=buffer_meters)
        
        if green_gdf.empty:
            print(f"No green spaces or natural areas found within a {buffer_meters}m radius.")
            return buffer_meters
            
        # 2. Combine all polygon and point geometries into a unified structural map
        all_green_areas = union_all(green_gdf.geometry)
        
        # 3. Calculate the closest point on the green boundaries to our target coordinate
        nearest_green_point, _ = nearest_points(all_green_areas, shapely_point)
        
        # 4. Transform to metric CRS (EPSG:3857) for accurate distance math
        transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
        x1, y1 = transformer.transform(shapely_point.x, shapely_point.y)
        x2, y2 = transformer.transform(nearest_green_point.x, nearest_green_point.y) # Cleaned line
        
        point_transformed = Point(x1, y1)
        green_transformed = Point(x2, y2)
        
        return round(point_transformed.distance(green_transformed), 2)

    except Exception as e:
        print(f"Green space infrastructure query status: {e}")
        return buffer_meters
    
def res_zone(shapely_point, buffer_meters=2000, house_threshold=8):
    """
    Evaluates if a coordinate point sits within a residential zone based on a 
    strict binary house-count threshold within a 2000m radius.
    
    Returns 1 if True (Is Residential), 0 if False.
    """
    lon = shapely_point.x
    lat = shapely_point.y
    
    residential_tags = {
        'building': ['house', 'detached', 'residential', 'semidetached', 'apartments']
    }
    
    try:
        # 1. Query building features within the designated radius
        center_point = (lat, lon)
        buildings_gdf = ox.features_from_point(center_point, tags=residential_tags, dist=buffer_meters)
        
        if buildings_gdf.empty:
            total_houses = 0
        else:
            total_houses = len(buildings_gdf)
            
        # 2. Apply binary conditional check
        is_residential = 1 if total_houses > house_threshold else 0
        return is_residential

    except Exception as e:
        # Gracefully catch empty zone API returns as 0
        if "No elements found" in str(e) or "found no features" in str(e).lower():
            return 0
        print(f"Residential check execution warning: {e}")
        return 0

def get_slope(shapely_point):

    lon = shapely_point.x
    lat = shapely_point.y

    # 1. Define the point of interest
    point = ee.Geometry.Point([lon, lat])
    
    # 2. Load the global SRTM Digital Elevation Model (30m resolution)
    elevation_model = ee.Image('USGS/SRTMGL1_003')
    
    # 3. Calculate terrain products (slope band is in degrees)
    terrain = ee.Terrain.products(elevation_model)
    slope_deg = terrain.select('slope')
    
    # 4. Convert slope from degrees to percentage: 100 * tan(degrees * pi / 180)
    # Using an EE image expression evaluates this efficiently on the cloud server
    slope_pct = slope_deg.expression(
        'tan(deg * pi / 180) * 100',
        {
            'deg': slope_deg,
            'pi': 3.141592653589793
        }
    ).rename('slope_percentage')
    
    # 5. Sample the pixel value at the exact coordinate
    sample = slope_pct.sample(point, scale=30).first().getInfo()
    
    if sample and 'properties' in sample:
        return sample['properties']['slope_percentage']
    else:
        return 0

def evaluate_values(params):

    initialize_ee()
    
    m_economics = extract_macro_economics(params['point'])
    macro_tier = m_economics['macro_economic_tier'] #tier 1 (high income), 2 (middle income), or 3 (low income)
    grid_status = eval_en_av(params['point']) #Stable, unstable or off grid

    match (macro_tier, grid_status['energy_grid_status']):
            # --- TIER 1: High Capacity ---
            case (1, "Stable_Grid_Connected"):
                socioeconomic_tier = 1
            # --- TIER 2: Medium-High Capacity ---
            case (1, "unstable") | (2, "Stable_Grid_Connected") | (2, "unstable"):
                socioeconomic_tier = 2
            # --- TIER 3: Medium-Low Capacity ---
            case (1, "Off-Grid / Isolated") | (2, "Off-Grid / Isolated") | (3, "Stable_Grid_Connected") | (3, "unstable"):
                socioeconomic_tier = 3
            # --- TIER 4: Low/Critical Capacity ---
            case (3, "Off-Grid / Isolated"):
                socioeconomic_tier = 4
            # --- Fallback/Error handling for unexpected data entries ---
            case _:
                print(f"Warning: Unexpected socioeconomic matrix combination: Tier {macro_tier}, Grid {grid_status}")
                socioeconomic_tier = 3 # Default safely to a moderate-low restriction fallback
    st.write(socioeconomic_tier)
    urban_st = urban_road_den(params['point'])
    urb_area = urban_st['is_urban']
    st.write(urb_area)
    d_road = dist_road(params['point'])
    st.write(d_road)
    slope = get_slope(params['point'])
    d_ptar = dist_ptar(params['point'])
    st.write(d_ptar)
    d_supply = dist_supply(params['point'])
    st.write(d_supply)
    d_energy = dist_pgrid(params['point'])
    st.write(d_energy)
    d_sewage = dist_sew(params['point'])
    st.write(d_sewage)
    d_parks = dist_green_area(params['point'])
    st.write(d_parks)
    r_zone = res_zone(params['point'])
    st.write(r_zone)
    peri_urb = 0 if urb_area == 1 else 1
    #Evaluate typical population densities in accordance with the type of project
    match str(params['project type']):
        case "Housing Unit under Horizontal Property Regime":
            population_density = 40 # Low density, unifamiliar houses/flats
        case "Residential Property with Lot Autonomy":
            population_density = 650 # High vertical density, buildings
        case "Community Residential Core":
            population_density = 250 # Medium-high consolidated urban density
        case "Large-Scale Urban Development Project":
            population_density = 450 # High planned density

    values = {
        'Proj_type': 1,
        'Socioeconomic_tier': socioeconomic_tier,
        'Sew_Dist': d_sewage,
        'Urb_area': urb_area,
        'Peri_urb': peri_urb,
        'Green_areas': d_parks,
        'Area': params['av_area'],
        'Dist_ptar': d_ptar,
        'Slope': slope,
        'En_grid': d_energy,
        'Population': params['population'],
        'Population_den': population_density,
        'Sup_grid': d_supply,
        'Dist_road': d_road,
        'Climate' : 1,
        'Res_zone': r_zone
    }
    st.write(values)
    return values

def to_excel(results):
    output = io.BytesIO()

    #Open the writer ONCE outside the loop
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Unpack dict keys (name) and values (sheet)
        for name, sheet in results.items():
            sheet.to_excel(writer, index=False, sheet_name=name)

    # The writer automatically saves and closes when exiting the 'with' block

    processed_data = output.getvalue()
    return processed_data