import osmnx as ox
import pandas as pd

# 1. Define the area (Brno city)
place_name = "Brno, Czechia"

# 2. Download the road network (all segments)
# 'drive' gets roads for cars. Use 'all' for everything (footpaths, etc.)
print(f"Downloading road segments for {place_name}...")
graph = ox.graph_from_place(place_name, network_type='drive')

# 3. Convert the graph (nodes/edges) to a GeoDataFrame
# We only need the 'edges' (the actual road segments)
nodes, edges = ox.graph_to_gdfs(graph)

# 4. Filter and Rename columns to match your format
# OSM uses slightly different tag names than your sample
# 'highway' = road_class, 'maxspeed' = max_speed, etc.
osm_data = edges.reset_index()

# Select and rename available columns
# Note: OSM data is messy; some columns might not exist if no road has that tag
column_mapping = {
    'osmid': 'osm_id',
    'name': 'name',
    'ref': 'road_ref',
    'highway': 'road_class',
    'maxspeed': 'max_speed'
}

# Keep only columns that exist in the downloaded data
available_cols = [c for c in column_mapping.keys() if c in osm_data.columns]
final_df = osm_data[available_cols].rename(columns=column_mapping)

# Add 'city' column manually
final_df['city'] = 'Brno'

# 5. Extract Geometry as Hex (WKB) to match your "geog" column
# This requires shapely (usually installed with geopandas)
from shapely import wkb
final_df['geog'] = edges['geometry'].apply(lambda x: x.wkb_hex).values

# 6. Save to CSV
final_df.to_csv('../brno_roads_updated.csv', index=False)
print(f"Success! Saved {len(final_df)} segments to brno_roads_updated.csv")