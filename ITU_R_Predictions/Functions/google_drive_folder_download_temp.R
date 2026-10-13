
#### First trial of google drive downloader function that downloads the contents of a complete folder

## Currently only able to go lower than working directory --> future improvements will come

google_drive_folder_download_temp <- function(folder_id, dest_id, overwrite_choice = F) {
  
  # Get working directory
  oldwd <- getwd()
  
  # Set new working directory where the files are going to be placed
  setwd(dir = paste0(oldwd, "/",dest_id))
  
  # Get a tibble containing all files in drive folder
  ls_tibble <- googledrive::drive_ls(googledrive::as_id(folder_id))
  
  # Now for each file in the folder, download and put in correct destination
  for (file_id in ls_tibble$id) {
    googledrive::drive_download(
      file = googledrive::as_id(file_id),
      overwrite = overwrite_choice
    )
  }
  
  # Set the working directory back to the initial working directory
  setwd(dir = oldwd)
}