import logging
import os
from urllib.parse import urljoin, urlparse

import requests
""" from data_2_dasch import (
    construct_payload,
    create_resource,
    get_project,
    get_resource,
    login,
) """

# Configuration
OMEKA_API_URL = os.getenv("OMEKA_API_URL", 'https://omeka.unibe.ch/api/')
KEY_IDENTITY = os.getenv("KEY_IDENTITY", 'v0ox897Nt3aYTI6j97nHgKP8evw4qmCU')
KEY_CREDENTIAL = os.getenv("KEY_CREDENTIAL", 't7vflBnj95A6cVoEVhescMSQD8XBm5RW')
ITEM_SET_ID = os.getenv("ITEM_SET_ID", '10780')

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
def extract_property(props, prop_id, as_uri=False, only_label=False):
    """Extracts a property value or URI from properties based on property ID."""
    for prop in props:
        if prop.get("property_id") == prop_id:
            if as_uri:
                return f"[{prop.get('o:label', '')}]({prop.get('@id', '')})"
            if only_label: 
                return prop.get('o:label', '')
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

