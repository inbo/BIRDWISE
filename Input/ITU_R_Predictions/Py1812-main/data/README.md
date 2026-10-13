# data
---

This folder should contain all necessary info of the study area for predictions of LoRa connectivity.
The following files are necessary:
- Bwk_Limburg_2023.shp: BWK shapefile with a column called bwk_hab with understandable description of the vegetation types
- dhmv_height_model.tif: TIFF file of digital surface model of study area 
	- Too large for github, should be downloaded (using R script in future)
- NPHK_hex_grid.shp: Shapefile of hexagonal grid of study area

--- 

Other fields are included as well for the comparison of ITU R predictions for measured locations with reality:
- locations_coords.csv: Specific locations of samplign phase 4.5 (Lieteberg Tower)
- sampling_notes_*.csv: data for which to simulate each location