import logging
import os
from urllib.parse import urljoin, urlparse

import requests
from data_2_dasch import (
    construct_payload,
    create_resource,
    get_project,
    get_ressource,
    login,
)

# Configuration
OMEKA_API_URL = os.getenv("OMEKA_API_URL")
KEY_IDENTITY = os.getenv("KEY_IDENTITY")
KEY_CREDENTIAL = os.getenv("KEY_CREDENTIAL")
ITEM_SET_ID = os.getenv("ITEM_SET_ID")

PROJECT_SHORT_CODE = os.getenv("PROJECT_SHORT_CODE", "0856")
API_HOST = os.getenv("API_HOST", "http://0.0.0.0:3333")
INGEST_HOST = os.getenv("INGEST_HOST", "http://0.0.0.0:3340")
DSP_USER = os.getenv("DSP_USER", "root@example.com")
DSP_PWD = os.getenv("DSP_PWD", "test")

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# --- Helper Functions for Data Extraction ---
def is_valid_url(url):
    """Checks if a URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def download_file(url, dest_path):
    """Downloads a file from a given URL to the specified destination path."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
    except requests.exceptions.RequestException as err:
        logging.error(f"File download error: {err}")
        raise


def get_paginated_items(url, params):
    """Fetches all items from a paginated API endpoint."""
    items = []
    while url:
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as err:
            logging.error(f"Error fetching items: {err}")
            break
        items.extend(response.json())
        url = response.links.get("next", {}).get("url")
        params = None

    return items


def get_items_from_collection(collection_id):
    """Fetches all items from a specified collection."""
    params = {
        "item_set_id": collection_id,
        "key_identity": KEY_IDENTITY,
        "key_credential": KEY_CREDENTIAL,
        "per_page": 100,
    }
    return get_paginated_items(urljoin(OMEKA_API_URL, "items"), params)


def get_media(item_id):
    """Fetches media associated with a specific item ID."""
    params = {"key_identity": KEY_IDENTITY, "key_credential": KEY_CREDENTIAL}
    return get_paginated_items(
        urljoin(OMEKA_API_URL, f"media?item_id={item_id}"), params
    )


# --- Data Extraction and Transformation Functions ---
def extract_property(props, prop_id, as_uri=False):
    """Extracts a property value or URI from properties based on property ID."""
    for prop in props:
        if prop.get("property_id") == prop_id:
            if as_uri:
                return f"[{prop.get('o:label', '')}]({prop.get('@id', '')})"
            return prop.get("@value", "")
    return ""


def extract_combined_values(props):
    """Combines text values and URIs from properties into a single list."""
    values = [
        prop.get("@value", "").replace(";", "&#59")
        for prop in props
        if "@value" in prop
    ]
    uris = [
        f"[{prop.get('o:label', '').replace(';', '&#59')}]({prop.get('@id', '').replace(';', '&#59')})"
        for prop in props
        if "@id" in prop
    ]
    return values + uris


def extract_combined_values_csv(props):
    """Combines text values and URIs into a semicolon-separated string."""
    combined = extract_combined_values(props)
    return ";".join(combined)


def download_thumbnail(image_url):
    """Downloads the thumbnail image if the URL is valid."""
    if image_url and is_valid_url(image_url):
        filename = os.path.basename(image_url)
        local_image_path = f"objects/{filename}"
        if not os.path.exists(local_image_path):
            download_file(image_url, local_image_path)
        return local_image_path
    return ""


def infer_display_template(format_value):
    """Infers the display template type based on the format value."""
    if "image" in format_value.lower():
        return "image"
    elif "pdf" in format_value.lower():
        return "pdf"
    elif "geo+json" in format_value.lower():
        return "geodata"
    else:
        return "record"


def extract_item_data(item):
    """Extracts relevant data from an item and downloads its thumbnail if available."""
    local_image_path = (
        download_thumbnail(item.get("thumbnail_display_urls", {}).get("large", ""))
        or "assets/img/no-image.svg"
    )

    # TODO adhere to DaSCH API spec
    return {
        "objectid": extract_property(item.get("dcterms:identifier", []), 10),
        "parentid": "",
        "title": extract_property(item.get("dcterms:title", []), 1),
        "description": extract_property(item.get("dcterms:description", []), 4),
        "subject": extract_combined_values(item.get("dcterms:subject", [])),
        "era": extract_property(item.get("dcterms:temporal", []), 41),
        "isPartOf": extract_combined_values(item.get("dcterms:isPartOf", [])),
        "creator": extract_combined_values(item.get("dcterms:creator", [])),
        "publisher": extract_combined_values(item.get("dcterms:publisher", [])),
        "source": extract_combined_values(item.get("dcterms:source", [])),
        "date": extract_property(item.get("dcterms:date", []), 7),
        "type": extract_property(item.get("dcterms:type", []), 8, as_uri=True),
        "format": extract_property(item.get("dcterms:format", []), 9),
        "extent": extract_property(item.get("dcterms:extent", []), 25),
        "language": extract_property(item.get("dcterms:language", []), 12),
        "relation": extract_combined_values(item.get("dcterms:relation", [])),
        "rights": extract_property(item.get("dcterms:rights", []), 15),
        "license": extract_property(item.get("dcterms:license", []), 49),
        "display_template": "compound_object",
        "object_location": "",
        "image_small": local_image_path,
        "image_thumb": local_image_path,
        "image_alt_text": item.get("o:alt_text", ""),
    }


def extract_media_data(media, item_dc_identifier):
    """Extracts relevant data from a media item associated with a specific item."""
    format_value = extract_property(media.get("dcterms:format", []), 9)
    display_template = infer_display_template(format_value)

    # Download the thumbnail image if available and valid
    local_image_path = download_thumbnail(
        media.get("thumbnail_display_urls", {}).get("large", "")
    )

    # Extract media data
    object_location = (
        media.get("o:original_url", "") if media.get("o:is_public", False) else ""
    )

    logging.info(f"Media ID: {media['o:id']}")
    logging.info(f"is_public: {media.get('o:is_public')}")

    # TODO adhere to DaSCH API spec
    return {
        "objectid": extract_property(media.get("dcterms:identifier", []), 10),
        "parentid": item_dc_identifier,
        "title": extract_property(media.get("dcterms:title", []), 1),
        "description": extract_property(media.get("dcterms:description", []), 4),
        "subject": extract_combined_values(media.get("dcterms:subject", [])),
        "era": extract_property(media.get("dcterms:temporal", []), 41),
        "isPartOf": extract_combined_values(media.get("dcterms:isPartOf", [])),
        "creator": extract_combined_values(media.get("dcterms:creator", [])),
        "publisher": extract_combined_values(media.get("dcterms:publisher", [])),
        "source": extract_combined_values(media.get("dcterms:source", [])),
        "date": extract_property(media.get("dcterms:date", []), 7),
        "type": extract_property(media.get("dcterms:type", []), 8, as_uri=True),
        "format": format_value,
        "extent": extract_property(media.get("dcterms:extent", []), 25),
        "language": extract_property(media.get("dcterms:language", []), 12),
        "relation": extract_combined_values(media.get("dcterms:relation", [])),
        "rights": extract_property(media.get("dcterms:rights", []), 15),
        "license": extract_property(media.get("dcterms:license", []), 49),
        "display_template": display_template,
        "object_location": object_location,
        "image_small": local_image_path,
        "image_thumb": local_image_path,
        "image_alt_text": media.get("o:alt_text", ""),
    }


# --- Main Processing Function ---
def main():
    # Fetch item data
    items_data = get_items_from_collection(ITEM_SET_ID)

    ##### WORKFLOW
    # get_project()
    token = login(DSP_USER, DSP_PWD)
    project_iri = get_project()
    # get list and list values TODO

    # for all sgb_OBJECTS (metadata)
    for item in items_data:
        # if metadata exists already (check with function get_resource())
        metadata_iri = get_ressource(token, "sgb_OBJECT", item.obejctid).get("@id")
        # if values are different
        # update values TODO
        # else
        # construct_payload() TODO
        # create_resource()
        payload = construct_payload(item)
        create_resource(project_iri, payload, token)
        media_data = get_media(item.get("o:id", ""))
        if media_data:
            # for all sgb_MEDIA (medien)
            for media in media_data:
                continue
                # if media exists already (check with function get_resource())
                # if values are different
                # update values TODO
                # else
                # get metadata_iri/parent_iri(get_ressource(token, "sgb_OBJECT", "abb123").get('@id'))
                # upload_file()
                # construct_payload() TODO
                # create_resource()
    # Process each item and associated media
    item_records, media_records = [], []
    for item in items_data:
        item_record = extract_item_data(item)
        # Check if the item has a DaSCH ID
        item_records.append(item_record)
        media_data = get_media(item.get("o:id", ""))
        if media_data:
            for media in media_data:
                media_records.append(extract_media_data(media, item_record["objectid"]))


if __name__ == "__main__":
    main()
