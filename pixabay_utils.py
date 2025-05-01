import logging
import itertools
from pathlib import Path
import requests
from time import sleep
from utils import Progressbar

# request timeout
TIMEOUT = 60

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(message)s'
    )

def get_json(url, params):
    try:
        r = requests.get(url, params, allow_redirects=False, timeout=TIMEOUT)
        logging.debug("json url - " +  r.url)
    except requests.exceptions.Timeout as err:
        logger.warning(err)
        return None

    try:
        return r
    except Exception as err:
        logger.warning(err)
        return None


def download_images(url):
    try:
        r = requests.get(url, allow_redirects=False, timeout=TIMEOUT)
        logging.debug("image url - " +  r.url)
    except requests.exceptions.Timeout as err:
        logger.warning(err)
        return None

    try:
        return r
    except Exception as err:
        logger.warning(err)
        return None

def get_available_images(API_URL, params, MIN_IMG_PER_PAGE):
    params_copy = params.copy()
    params_copy["page"] = 1
    params_copy["per_page"] = MIN_IMG_PER_PAGE
    response = get_json(API_URL, params_copy)
    if response is None:
        return 0
    j_response = response.json()
    return j_response["total"]

def scraper(api_key, img_classes, path="img", images=1, image_type="photo", orientation="all", 
           category=None, min_width=0, min_height=0, colors=None, editors_choice=False, 
           safesearch=False, order="popular", lang="en", file_type="jpg", progress_callback=None):
    """
    Download images from Pixabay API
    
    Parameters:
    -----------
    api_key : str
        Your Pixabay API key
    img_classes : list
        List of search terms to download
    path : str
        Directory to save images to
    images : int
        Number of images to download per class
    image_type : str
        Type of image to download ("photo", "illustration", "vector", or "all")
    orientation : str
        Orientation of images ("horizontal", "vertical", or "all")
    category : str
        Category to filter by (e.g., "backgrounds", "nature", "people", etc.)
    min_width : int
        Minimum width of images in pixels
    min_height : int
        Minimum height of images in pixels
    colors : str
        Colors to filter by (comma-separated, e.g., "red,blue,green")
    editors_choice : bool
        Whether to only include images selected by Pixabay editors
    safesearch : bool
        Whether to enable safesearch to filter out adult content
    order : str
        Order to sort by ("popular" or "latest")
    lang : str
        Language code for search results
    file_type : str
        File extension to save images as (jpg, png, etc.)
    progress_callback : function
        Optional callback function to report progress.
        Called with (current_class, class_index, images_downloaded)
    """
    logger.debug((api_key, img_classes, path, images))
    # go to https://pixabay.com/api/docs/ to look up these values
    MAX_IMG_PER_PAGE = 200
    MIN_IMG_PER_PAGE = 3
    API_URL = "https://pixabay.com/api/"

    params = {
        "key": api_key,
        "q": "None",
        "image_type": image_type,
        "orientation": orientation,
        "order": order,
        "page": 1,
        "per_page": MAX_IMG_PER_PAGE,
        "lang": lang,
        "safesearch": "true" if safesearch else "false",
        "editors_choice": "true" if editors_choice else "false",
        "min_width": min_width,
        "min_height": min_height
    }
    
    # Add optional parameters if provided
    if category:
        params["category"] = category
    if colors:
        params["colors"] = colors

    path = Path(path)

    logger.info("Starting")

    total_downloaded = 0

    for class_idx, img_class in enumerate(img_classes):
        try:
            params["q"] = img_class

            try:
                class_path = path / img_class
                class_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"Something went wrong while creating path for {img_class}: {e}")
                continue

            logger.info(f"Downloading class: {img_class} to {class_path}")

            # testing if pixabay can serve the amount of wanted images
            available_images = get_available_images(API_URL, params, MIN_IMG_PER_PAGE)
            if available_images == 0:
                logger.warning(f"No images found for '{img_class}'")
                continue
            
            if available_images < images:
                logger.info(f"There are only {available_images} available images... starting download")
                images_to_download = available_images
            else:
                images_to_download = images

            Pbar = Progressbar(images_to_download, name=img_class)

            # creating the params list for all pages
            images_downloaded = 0
            run = True

            for page in itertools.count(1):
                try:
                    if not run:
                        break

                    params["page"] = page
                    response = get_json(API_URL, params)
                    if response is None:
                        logger.warning(f"Failed to get results for page {page}")
                        break
                        
                    j_response = response.json()
                    
                    # Break if no more images
                    if not j_response.get("hits"):
                        break

                    for image in j_response["hits"]:
                        try:
                            if images_downloaded >= images_to_download:
                                run = False
                                break

                            image_id = image["id"]
                            # Choose between different image sizes available
                            image_url = image.get("largeImageURL")
                            
                            if image_url is None:
                                logger.warning(f"No image URL for image {image_id}")
                                continue
                                
                            image_response = download_images(image_url)
                            if image_response is None:
                                logger.warning(f"Failed to download image {image_id}")
                                continue
                                
                            image_bytes = image_response.content

                            image_path = class_path / f"{image_id}.{file_type}"
                            with open(image_path, "wb") as file:
                                logger.debug(image_path)
                                file.write(image_bytes)

                            images_downloaded += 1
                            total_downloaded += 1
                            Pbar.set(images_downloaded)
                            
                            # Report progress via callback if provided
                            if progress_callback:
                                progress_callback(img_class, class_idx, images_downloaded)
                            
                            # Add a small delay to avoid overwhelming the API
                            sleep(0.1)

                        except Exception as err:
                            logger.warning(f"An error occurred processing image {image.get('id', 'unknown')}: {err}")

                except Exception as err:
                    logger.warning(f"An error occurred processing page {page}: {err}")
                    logger.warning(f"Downloaded {images_downloaded} images from {img_class}")
                    break

            logger.info(f"Completed downloading {images_downloaded} images for '{img_class}'")

        except Exception as err:
            logger.warning(f"An error occurred processing the class {img_class}: {err}")
    
    logger.info(f"Download complete. Total images downloaded: {total_downloaded}")
    return total_downloaded
