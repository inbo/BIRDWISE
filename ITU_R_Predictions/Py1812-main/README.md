# Py1812-main: Python script to use ITU R 1812 model
---

This folder contains the entire repo of Py1812-main which holds python scripts to use the ITU-R 1812 model for predicting LoRa coverage based on hardware characteristics and environmental data

---

## How to use using R:
In order to run this model using R:
- Open R in this repo's project
- Open Prediction_ITUR.Rmd
- Alter input specifications in script by choice
- Run python script using R (Chunk 6)
- Ouput in "LoRaWAN_performance_testing/Intermediate/Predictions/NPHK_ITU_coverage.shp" --> can be analysed using R script as well

---

## How to use using command prompt:
In order to run this script locally:
- Open command prompt
- Move to this folder using "cd \INDIVIDUAL\PATH\Py1812-main"
- Type "py heatmap_builder_original.py"
- Direct output in console and in shapefile "NPHK_ITU_Coverage_DATETIME.shp" and "coverage_test_TIME.csv"

---