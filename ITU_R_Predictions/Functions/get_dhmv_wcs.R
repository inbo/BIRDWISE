library(httr2)
library(terra)

get_dhmv_wcs <- function(coverage = c("DHMVII_DTM_1m", "DHMVII_DSM_1m"),
                         xmin, xmax, ymin, ymax,
                         resolution = 1,
                         out_file = tempfile(fileext = ".tif")) {
  coverage <- match.arg(coverage)
  width  <- round((xmax - xmin) / resolution)
  height <- round((ymax - ymin) / resolution)
  
  req <- request("https://geo.api.vlaanderen.be/DHMV/wcs") |>
    req_url_query(
      SERVICE = "WCS", VERSION = "1.0.0", REQUEST = "GetCoverage",
      COVERAGE = coverage, FORMAT = "GeoTIFF",
      BBOX = paste(xmin, ymin, xmax, ymax, sep = ","),
      CRS = "EPSG:31370", RESPONSE_CRS = "EPSG:31370",
      WIDTH = width, HEIGHT = height
    )
  
  req_perform(req, path = out_file)
  rast(out_file)
}

get_dhmv_wcs_tiled <- function(coverage, bbox, resolution = 1, tile_size = 2000) {
  # bbox: named vector xmin, ymin, xmax, ymax (e.g. from sf::st_bbox)
  xs <- seq(bbox["xmin"], bbox["xmax"], by = tile_size)
  ys <- seq(bbox["ymin"], bbox["ymax"], by = tile_size)
  
  tiles <- list()
  for (x0 in xs) {
    for (y0 in ys) {
      x1 <- min(x0 + tile_size, bbox["xmax"])
      y1 <- min(y0 + tile_size, bbox["ymax"])
      if (x1 <= x0 || y1 <= y0) next
      
      message(sprintf("Fetching tile x[%s,%s] y[%s,%s]", x0, x1, y0, y1))
      tiles[[length(tiles) + 1]] <- get_dhmv_wcs(
        coverage, xmin = x0, xmax = x1, ymin = y0, ymax = y1,
        resolution = resolution
      )
    }
  }
  
  do.call(mosaic, c(tiles, fun = "first"))
}