# ITU R Predictions for LoRaWAN infrastructure planning
---

## Structure
---

Structure of this folder:
- Functions
- Input
- Intermediate
- Output
- Py1812-main
- python_env
- Rscripts

---

## Prediction protocol
---

Making predictions using ITU R model (Everything in this folder)
1. Add gateway locations you want to simulate in Flanders in Input/stduy_area.csv following example
2. Open "Preparatory_steps_ITUR_predictions.Rmd" within Rscripts
3. Alter the necessary study area selected and distance that is simulated
4. Run the complete script
5. Open "Predictions_ITUR.Rmd" within Rscripts
6. Change the study area selected and simulated data the same as before, other parameters of the model can be altered here as well
7. Run the complete script 
8. The output can be found in the script and in "Intermediate"
