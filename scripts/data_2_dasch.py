import argparse
from argparse import Namespace
import urllib
from pathlib import Path
import random
from typing import cast
import tempfile

import logging
import os

import requests

from process_data_from_omeka import (
    get_items_from_collection,
    get_media,
    extract_combined_values,
    extract_property
)

# TODO: - error handling
#       - logging
#       - refactoring

# Configuration
OMEKA_API_URL = os.getenv("OMEKA_API_URL")
KEY_IDENTITY = os.getenv("KEY_IDENTITY")
KEY_CREDENTIAL = os.getenv("KEY_CREDENTIAL")
ITEM_SET_ID = os.getenv("ITEM_SET_ID")

PROJECT_SHORT_CODE = os.getenv("PROJECT_SHORT_CODE")
API_HOST = os.getenv("API_HOST")
INGEST_HOST = os.getenv("INGEST_HOST")
DSP_USER = os.getenv("DSP_USER")
DSP_PWD = os.getenv("DSP_PWD")
PREFIX = os.getenv("PREFIX", "StadtGeschichteBasel_v1:")

NUMBER_RANDOM_OBJECTS = 2
TEST_DATA = {'abb13025', 'abb14375'}

# Set up logging
file_handler = logging.FileHandler("data_2_dasch.log", mode='w')
file_handler.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[stream_handler, file_handler]
)


def parse_arguments() -> Namespace:
    """Parses the commandline for the path to the config-file and for the path to the output directory.

    Returns:
        Namespace: Argparse-Namespace object
    """

    parser = argparse.ArgumentParser(description="--mode")
    parser.add_argument("-m", "--mode", type=str, choices=['all_data', 'sample_data', 'test_data'], default='all_data',
                        help=f"which data should be processed? possible options: 'all_data' (all data), 'sample_data' ({NUMBER_RANDOM_OBJECTS} random metadata objects),'test_data' (10 selected test metadata objects)")
    args = parser.parse_args()

    return args


def login(email: str, password: str) -> str:
    endpoint = f"{API_HOST}/v2/authentication"
    response = requests.post(endpoint, json={"email": email, "password": password}, timeout=10)
    logging.info("Login successful")
    return cast(str, response.json()["token"])

def get_project():
    endpoint = f"{API_HOST}/admin/projects/shortcode/{PROJECT_SHORT_CODE}"
    response = requests.get(endpoint)
    if response.status_code == 200:
        logging.info(f"project Iri: {cast(str, response.json()["project"]["id"])}")
    else:
        logging.error(f"Failed to retrieve project. Status code: {response.status_code}")
        logging.error(f"Response: {response.text}")
    return cast(str, response.json()["project"]["id"])

# Get lists
def get_lists(project_iri):
    url_lists = f"{API_HOST}/admin/lists/?projectIri={project_iri}"
    response_lists = requests.get(url_lists)
    if response_lists.status_code == 200:
        all_lists = []
        for list in response_lists.json()["lists"]:
            list_id = list["id"]
            # URL encode the list IRI
            encoded_list_id = urllib.parse.quote(list_id, safe='')
            # Construct the API endpoint for this specific list ID
            url = f"{API_HOST}/v2/lists/{encoded_list_id}"
            response = requests.get(url)
            if response.status_code == 200:
                all_lists.append(response.json())
            else:
                logging.error(f"Failed to retrieve complete list for {list_id}. Status code: {response.status_code}")
                logging.error(f"Response:{response.text}")
        logging.info(f"Got Lists from project")
    else:
        logging.error(f"Failed to retrieve lists. Status code: {response.status_code}")
        logging.error(f"Response: {response.text}")
    return all_lists


def get_full_resource(token: str, resource_iri: str) -> dict:
    endpoint = f"{API_HOST}/v2/resources/{resource_iri}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(endpoint, headers=headers)
    return response.json()

def extract_dasch_propvalue(item, prop):

    full_property = f"{PREFIX}{prop}"
    if full_property in item:
        prop_value = item[full_property]
        return extract_value_from_entry(prop_value)
    return ""

def extract_dasch_propvalue_multiple(item, prop):
    full_property = f"{PREFIX}{prop}"
    values = []
    # Get the value(s) of the property, either as a list or a single entry
    prop_values = item.get(full_property)
    # If the property exists and is either a list or a dict (single value case)
    if prop_values:
        # If the property is a list, iterate over the entries
        if isinstance(prop_values, list):
            for entry in prop_values:
                value = extract_value_from_entry(entry)
                if value:
                    values.append(value)
        # If it's a single dictionary (not a list), extract the value directly
        elif isinstance(prop_values, dict):
            value = extract_value_from_entry(prop_values)
            if value:
                values.append(value)
    return values

def extract_value_from_entry(entry):
    entry_type = entry.get('@type')
    value = None
    
    if entry_type == "knora-api:TextValue":
        value = entry.get("knora-api:valueAsString")
    elif entry_type == "knora-api:ListValue":
        value = entry.get("knora-api:listValueAsListNode", {}).get("@id")
    elif entry_type == "knora-api:LinkValue":
        value = entry.get("knora-api:linkValueHasTargetIri", {}).get("@id")
    elif entry_type == "knora-api:UriValue":
        value = entry.get("knora-api:uriValueAsUri", {}).get("@value")
    return value

def get_resource_by_id(token: str, object_class: str, identifier: str) -> dict:
    endpoint = f"{API_HOST}/v2/searchextended"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/sparql-query; charset=utf-8"
    }
    query = f"""
        PREFIX knora-api: <http://api.knora.org/ontology/knora-api/v2#>
        PREFIX {PREFIX} <{API_HOST}/ontology/{PROJECT_SHORT_CODE}/StadtGeschichteBasel_v1/v2#>
        CONSTRUCT {{
            ?metadata knora-api:isMainResource true .
            ?metadata {PREFIX}identifier ?identifierValue .
            ?metadata {PREFIX}title ?title .
        }} WHERE {{
            ?metadata a {object_class} .
            ?metadata {PREFIX}identifier ?identifierValue .
            ?identifierValue knora-api:valueAsString ?identifier .
            ?metadata {PREFIX}title ?title .
            FILTER(?identifier = "{identifier}")
        }}
        """
    response = requests.post(endpoint, data=query.encode('utf-8'), headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Error: {response.status_code}")
        logging.error(response.text)
        return {}


def update_value(token, item, value, field, field_type, type_of_change):

    context_data = {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "knora-api": "http://api.knora.org/ontology/knora-api/v2#",
        "StadtGeschichteBasel_v1": API_HOST + "/ontology/" + PROJECT_SHORT_CODE + "/StadtGeschichteBasel_v1/v2#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#"
    }   
    complete_field_type = f"knora-api:{field_type}"
    payload = {
        "@context": context_data,
        "@id": item["@id"],
        "@type": item["@type"],
        f"{PREFIX}{field}": {
            "@type": complete_field_type
        }
    }

    if type_of_change in ["delete", "update"]:
        if isinstance(item[f"{PREFIX}{field}"], dict):
            value_id = item[f"{PREFIX}{field}"]["@id"]
        elif isinstance(item[f"{PREFIX}{field}"], list):
            for obj in item[f"{PREFIX}{field}"]:
                if field_type == "TextValue" and obj.get("knora-api:valueAsString") == value:
                    value_id = obj["@id"]
                    break
                elif field_type == "ListValue" and obj.get("knora-api:listValueAsListNode", {}).get("@id") == value:
                    value_id = obj["@id"]
                    break
                elif field_type == "UriValue" and obj.get("knora-api:uriValueAsUri", {}).get("@value") == value:
                    value_id = obj["@id"]
                    break
        payload[f"{PREFIX}{field}"]["@id"] = value_id
    
    if type_of_change in ["create", "update"]:
        if field_type == "TextValue":
            payload[f"{PREFIX}{field}"]["knora-api:valueAsString"] = value
        if field_type == "ListValue":
            payload[f"{PREFIX}{field}"]["knora-api:listValueAsListNode"] = {
                "@id": value
            }
        if field_type == "UriValue":
            payload[f"{PREFIX}{field}"]["knora-api:uriValueAsUri"] = {
                "@value": value,
                "@type": "http://www.w3.org/2001/XMLSchema#anyURI"
            }
        if field_type == "linkvalue":
            payload[f"{PREFIX}{field}"]["knora-api:linkValueHasTargetIri"] = {
                "@id": value 
            }

    if type_of_change == "delete":
        endpoint = f"{API_HOST}/v2/values/delete"
    else:
        endpoint = f"{API_HOST}/v2/values"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Asset-Ingested": "true",
    }

    if type_of_change == "update":
        response = requests.put(endpoint, json=payload, headers=headers, timeout=10)
    else:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)

    if response.status_code == 200:
        logging.info(f"{item[f"{PREFIX}identifier"]["knora-api:valueAsString"]}: {type_of_change}d {field} '{value}'")
    else:
        logging.error(f"{item[f"{PREFIX}identifier"]["knora-api:valueAsString"]}: update of {field} failed: {response.status_code}: {response.text}")
        # logging.error(payload)

def arrays_equal(array1, array2):
    if len(array1) != len(array2):
        return False
    return set(array1) == set(array2)

def sync_value(prop, prop_type, dasch_value, omeka_value):
    if dasch_value == "" and omeka_value != "":
        return {"field": prop, "prop_type": prop_type, "type": "create", "value": omeka_value}
    elif dasch_value != "" and omeka_value == "":
        return {"field": prop, "prop_type": prop_type, "type": "delete", "value": omeka_value}
    elif dasch_value != "" and omeka_value != "" and dasch_value != omeka_value:
        return {"field": prop, "prop_type": prop_type, "type": "update", "value": omeka_value}


def sync_array_value(prop, prop_type, dasch_array, omeka_array):
    dasch_set = set(dasch_array)
    omeka_set = set(omeka_array)

    to_create = omeka_set - dasch_set  
    to_delete = dasch_set - omeka_set  

    changes = [{"field": prop, "prop_type": prop_type, "type": "create", "value": value} for value in to_create]
    changes += [{"field": prop, "prop_type": prop_type, "type": "delete", "value": value} for value in to_delete]

    return changes


def check_values(dasch_item, omeka_item, lists):
    modified_values = []
    title = sync_value("title", "TextValue", extract_dasch_propvalue(dasch_item, "title"),extract_property(omeka_item.get("dcterms:title", []), 1))
    if title: modified_values.append(title)
    description = sync_value("description", "TextValue", extract_dasch_propvalue(dasch_item, "description"),extract_property(omeka_item.get("dcterms:description", []), 4))
    if description: modified_values.append(description)
    subjects = []
    for data in extract_combined_values(omeka_item.get("dcterms:subject", [])):
        subject = extract_listvalueiri_from_value(data, "Thema", lists)
        subjects.append(subject)
    subject = sync_array_value("subject", "ListValue", extract_dasch_propvalue_multiple(dasch_item, "subject"), subjects)
    if subject: modified_values.extend(subject)
    temporal = sync_value("temporal", "ListValue", extract_dasch_propvalue(dasch_item, "temporal"),extract_listvalueiri_from_value(extract_property(omeka_item.get("dcterms:temporal", []), 41), "Era", lists))
    if temporal: modified_values.append(temporal)
    language = sync_value("language", "TextValue", extract_dasch_propvalue(dasch_item, "language"),extract_property(omeka_item.get("dcterms:language", []), 12))
    if language: modified_values.append(language)

    # Check object specific fields  
    if dasch_item["@type"] == f"{PREFIX}sgb_OBJECT":
        isPartOf = sync_array_value("isPartOf", "TextValue", extract_dasch_propvalue_multiple(dasch_item, "isPartOf"), extract_combined_values(omeka_item.get("dcterms:isPartOf", [])))
        if isPartOf: modified_values.extend(isPartOf)

    # Check media specific fields
    if dasch_item["@type"].startswith(f"{PREFIX}sgb_MEDIA"):
        creator = sync_array_value("creator", "TextValue", extract_dasch_propvalue_multiple(dasch_item, "creator"), extract_combined_values(omeka_item.get("dcterms:creator", [])))
        if creator: modified_values.extend(creator)
        publisher = sync_array_value("publisher", "TextValue", extract_dasch_propvalue_multiple(dasch_item, "publisher"), extract_combined_values(omeka_item.get("dcterms:publisher", [])))
        if publisher: modified_values.extend(publisher)
        date = sync_value("date", "TextValue", extract_dasch_propvalue(dasch_item, "date"),extract_property(omeka_item.get("dcterms:date", []), 7))
        if date: modified_values.append(date)
        extent = sync_value("extent", "TextValue", extract_dasch_propvalue(dasch_item, "extent"),extract_property(omeka_item.get("dcterms:extent", []), 25))
        if extent: modified_values.append(extent)
        type = sync_value("type", "ListValue", extract_dasch_propvalue(dasch_item, "type"),extract_listvalueiri_from_value(extract_property(omeka_item.get("dcterms:type", []), 8, only_label=True), "DCMI Type Vocabulary", lists))
        if type: modified_values.append(type)
        format = sync_value("format", "ListValue", extract_dasch_propvalue(dasch_item, "format"),extract_listvalueiri_from_value(extract_property(omeka_item.get("dcterms:format", []), 9), "Internet Media Type", lists))
        if format: modified_values.append(format)
        source = sync_array_value("source", "TextValue", extract_dasch_propvalue_multiple(dasch_item, "source"), extract_combined_values(omeka_item.get("dcterms:source", [])))
        if source: modified_values.extend(source)
        relation = sync_array_value("relation", "TextValue", extract_dasch_propvalue_multiple(dasch_item, "relation"), extract_combined_values(omeka_item.get("dcterms:relation", [])))
        if relation: modified_values.extend(relation)
        rights = sync_value("rights", "TextValue", extract_dasch_propvalue(dasch_item, "rights"),extract_property(omeka_item.get("dcterms:rights", []), 15))
        if rights: modified_values.append(rights)
        license = sync_value("license", "UriValue", extract_dasch_propvalue(dasch_item, "license"),extract_property(omeka_item.get("dcterms:license", []), 49))
        if license: modified_values.append(license)

    return modified_values
    

def extract_listvalueiri_from_value(value, list_label, lists):
        reference = next((list for list in lists if list["rdfs:label"] == list_label), None)
        sublist = reference["knora-api:hasSubListNode"]
        match = next((node for node in sublist if node["rdfs:label"] == value), None)
        if match:
            return match["@id"]
        else:
            logging.warning(f"No match found for value: '{value}' in list: {list_label}")

def construct_payload(item, type, project_iri, lists, parent_iri, internalMediaFilename):
    context_data = {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "knora-api": "http://api.knora.org/ontology/knora-api/v2#",
        "StadtGeschichteBasel_v1": API_HOST + "/ontology/" + PROJECT_SHORT_CODE + "/StadtGeschichteBasel_v1/v2#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#"
    }
    
    # Build initial payload structure
    payload = {
        "@context": context_data,
        "@type": type,
        "knora-api:attachedToProject": {
            "@id": project_iri
        },
        "rdfs:label": extract_property(item.get("dcterms:title", []), 1),
        f"{PREFIX}identifier": {
            "knora-api:valueAsString": extract_property(item.get("dcterms:identifier", []), 10),
            "@type": "knora-api:TextValue"
        },
        f"{PREFIX}title": {
            "knora-api:valueAsString": extract_property(item.get("dcterms:title", []), 1),
            "@type": "knora-api:TextValue"
        }
    }
    payload[f"{PREFIX}description"] = {
        "knora-api:valueAsString": extract_property(item.get("dcterms:description", []), 4),
        "@type": "knora-api:TextValue"
    }
    if 'dcterms:subject' in item:
        subjects = []
        for data in extract_combined_values(item.get("dcterms:subject", [])):
            subject = extract_listvalueiri_from_value(data, "Thema", lists)
            if subject:
                subjects.append({
                "@type": "knora-api:ListValue",
                "knora-api:listValueAsListNode": {
                    "@id": subject
            }})
        payload[f"{PREFIX}subject"] = subjects
    if 'dcterms:temporal' in item:
        temporal = extract_listvalueiri_from_value(extract_property(item.get("dcterms:temporal", []), 41), "Era", lists)
        if temporal:
            payload[f"{PREFIX}temporal"] = {
                "@type": "knora-api:ListValue",
                "knora-api:listValueAsListNode": {
                    "@id": temporal
                }
            }
    if extract_property(item.get("dcterms:language", []), 12):
        payload[f"{PREFIX}language"] =  {
            "knora-api:valueAsString": extract_property(item.get("dcterms:language", []), 12),
            "@type": "knora-api:TextValue"
        }
    if 'dcterms:isPartOf' in item:
        isPartOf = []
        for data in extract_combined_values(item.get("dcterms:isPartOf", [])): 
            isPartOf.append({
                "knora-api:valueAsString": data,
                "@type": "knora-api:TextValue"
            })
        payload[f"{PREFIX}isPartOf"] = isPartOf
         
    # Handle MEDIA type-specific fields
    if type == f"{PREFIX}sgb_MEDIA_IMAGE":
        payload["knora-api:hasStillImageFileValue"] =  {
            "@type": "knora-api:StillImageFileValue",
            "knora-api:fileValueHasFilename": internalMediaFilename
        }
    if type == f"{PREFIX}sgb_MEDIA_ARCHIV":
        payload["knora-api:hasArchiveFileValue"] =  {
            "@type": "knora-api:ArchiveFileValue",
            "knora-api:fileValueHasFilename": internalMediaFilename
        }
    if type == f"{PREFIX}sgb_MEDIA_DOCUMENT":
        payload["knora-api:hasDocumentFileValue"] =  {
            "@type": "knora-api:DocumentFileValue",
            "knora-api:fileValueHasFilename": internalMediaFilename
        }
    if type == f"{PREFIX}sgb_MEDIA_TEXT":
        payload["knora-api:hasTextFileValue"] =  {
            "@type": "knora-api:TextFileValue",
            "knora-api:fileValueHasFilename": internalMediaFilename
        }
    if type.startswith(f"{PREFIX}sgb_MEDIA"):

        payload[f"{PREFIX}partOf_MetadataValue"] = {
            "@type": "knora-api:LinkValue",
            "knora-api:linkValueHasTargetIri": {
                "@id": parent_iri
            }
        }
        if 'dcterms:date' in item:
            payload[f"{PREFIX}date"] = {
                "knora-api:valueAsString": extract_property(item.get("dcterms:date", []), 7),
                "@type": "knora-api:TextValue"
            }       
        mediatype = extract_listvalueiri_from_value(extract_property(item.get("dcterms:type", []), 8, only_label=True), "DCMI Type Vocabulary", lists)
        if mediatype:
            payload[f"{PREFIX}type"] = {
                "@type": "knora-api:ListValue",
                "knora-api:listValueAsListNode": {
                    "@id": mediatype
                }
            }
        format = extract_listvalueiri_from_value(extract_property(item.get("dcterms:format", []), 9), "Internet Media Type", lists)
        if format:
            payload[f"{PREFIX}format"] = {
                "@type": "knora-api:ListValue",
                "knora-api:listValueAsListNode": {
                    "@id": format
                }
            }
        if 'dcterms:extent' in item:
            payload[f"{PREFIX}extent"] = {
                "knora-api:valueAsString": extract_property(item.get("dcterms:extent", []), 25),
                "@type": "knora-api:TextValue"
            }
        if 'dcterms:rights' in item:
            payload[f"{PREFIX}rights"] = {
                "knora-api:valueAsString": extract_property(item.get("dcterms:rights", []), 15),
                "@type": "knora-api:TextValue"
            }
        if 'dcterms:license' in item:
            payload[f"{PREFIX}license"] = {
                "@type": "knora-api:UriValue",
		        "knora-api:uriValueAsUri": {
			        "@value": extract_property(item.get("dcterms:license", []), 49),
			        "@type": "http://www.w3.org/2001/XMLSchema#anyURI"
		        }
	        }
        if 'dcterms:creator' in item:
            creators = []
            for data in extract_combined_values(item.get("dcterms:creator", [])): 
                creators.append({
                    "knora-api:valueAsString": data,
                    "@type": "knora-api:TextValue"
                })
            payload[f"{PREFIX}creator"] = creators
        if 'dcterms:publisher' in item:
            publishers = []
            for data in extract_combined_values(item.get("dcterms:publisher", [])): 
                publishers.append({
                    "knora-api:valueAsString": data,
                    "@type": "knora-api:TextValue"
                })
            payload[f"{PREFIX}publisher"] = publishers
        if 'dcterms:source' in item:
            sources = []
            for data in extract_combined_values(item.get("dcterms:source", [])): 
                sources.append({
                    "knora-api:valueAsString": data,
                    "@type": "knora-api:TextValue"
                })
            payload[f"{PREFIX}source"] = sources
        if 'dcterms:relation' in item:
            relations = []
            for data in extract_combined_values(item.get("dcterms:relation", [])): 
                relations.append({
                    "knora-api:valueAsString": data,
                    "@type": "knora-api:TextValue"
                })
            payload[f"{PREFIX}relation"] = relations

    return payload

def upload_file_from_url(file_url: str, token: str) -> str:
    """
    Downloads a file from a URL and uploads it to the specified endpoint.

    Args:
        file_url (str): The URL of the file to be uploaded.
        token (str): The authentication token for the upload endpoint.

    Returns:
        str: The internal filename returned by the upload endpoint.
    """
    # Download the file from the URL
    try:
        response = requests.get(file_url, stream=True, timeout=10)
    except requests.exceptions.RequestException as err:
        logging.error(f"File download error: {err}")
        raise     
    # Extract the original filename from the URL
    original_filename = Path(urllib.parse.urlparse(file_url).path).name
    if not original_filename:
        raise ValueError("The file URL does not contain a valid filename.")

    # Save the file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(response.content)
        temp_file_path = Path(temp_file.name)

    # Prepare the upload
    encoded_filename = urllib.parse.quote(original_filename)
    endpoint = f"{INGEST_HOST}/projects/{PROJECT_SHORT_CODE}/assets/ingest/{encoded_filename}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }
    
    try:
        # Upload the file
        with open(temp_file_path, "rb") as file_data:
            upload_response = requests.post(endpoint, data=file_data, headers=headers, timeout=30)
        
        # Clean up the temporary file
        temp_file_path.unlink()

        # Handle the response
        if upload_response.status_code == 200:
            return cast(str, upload_response.json()["internalFilename"])
        else:
            logging.error(
                f"Unexpected response status {upload_response.status_code}: "
                f"{upload_response.text}"
            )
            return None
    except requests.exceptions.RequestException as err:
        logging.error(f"File upload error: {err}")
   
    return None


def create_resource(payload: dict, token: str) -> None:
    # https://docs.dasch.swiss/latest/DSP-API/03-endpoints/api-v2/editing-resources/#creating-a-resource
    resources_endpoint = f"{API_HOST}/v2/resources"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Asset-Ingested": "true",
    }

    response = requests.post(resources_endpoint, json=payload, headers=headers, timeout=10)
    if response.status_code == 200:
        logging.info(f"{payload[f"{PREFIX}identifier"]["knora-api:valueAsString"]}: resource created on DaSCH")
    else:
        logging.error(f"{payload[f"{PREFIX}identifier"]["knora-api:valueAsString"]}: resource creation failed: {response.status_code}: {response.text}")
        logging.error(payload)


def specify_mediaclass(media_type: str) -> str:
    valid_images_types = {"image/tiff", "image/jpg", "image/jpeg", "image/png", "image/gif"}
    valid_text_types = {"text/csv", "text/markdown", "text/plain", "application/json"}
    valid_doc_types = {"application/pdf"}
    if media_type in valid_images_types:
        return f"{PREFIX}sgb_MEDIA_IMAGE"
    if media_type in valid_text_types:
        return f"{PREFIX}sgb_MEDIA_TEXT"
    if media_type in valid_doc_types:
        return f"{PREFIX}sgb_MEDIA_DOCUMENT"
    # TODO: StadtGeschichteBasel_v1:sgb_MEDIA_ARCHIV (e.g. for geojson)
    else:
        
        return None
    

def main() -> None:

    args = parse_arguments()

    # Fetch item data
    items_data = get_items_from_collection(ITEM_SET_ID)

    if args.mode == 'sample_data':
        items_data = random.sample(items_data, NUMBER_RANDOM_OBJECTS)

    if args.mode == 'test_data':
        found_objects = []
        remaining_identifiers = TEST_DATA.copy()

        for obj in items_data:
            for identifier in obj.get('dcterms:identifier', []):
                if identifier['@value'] in remaining_identifiers:
                    found_objects.append(obj)
                    remaining_identifiers.remove(identifier['@value'])
                    
            if not remaining_identifiers:
                break
        items_data = found_objects

    # get_project()
    token = login(DSP_USER, DSP_PWD)
    project_iri = get_project()
    # get list and list values
    project_lists = get_lists(project_iri)

    for item in items_data:
        item_id = extract_property(item.get("dcterms:identifier", []), 10)
        metadata_iri = get_resource_by_id(token, f"{PREFIX}sgb_OBJECT", item_id).get('@id')
        if metadata_iri:
            object = get_full_resource(token, urllib.parse.quote(metadata_iri, safe=''))

            if 'knora-api:lastModificationDate' in object:
                dasch_date = object['knora-api:lastModificationDate']['@value']
            else:
                dasch_date = object['knora-api:creationDate']['@value']
            if item['o:modified']['@value'] > dasch_date:
                logging.info(f"{item_id}: object exists already, but it was modified. Update object ...")
                modified_values = check_values(object, item, project_lists)
                # print(modified_values)
                for value in modified_values:
                    update_value(token, object,value["value"],value["field"],value["prop_type"],value["type"])
            else:
                logging.info(f"{item_id}: object exists already")
                
        else:
            payload = construct_payload(item, f"{PREFIX}sgb_OBJECT", project_iri, project_lists,"","")
            create_resource(payload, token)
            metadata_iri = get_resource_by_id(token, f"{PREFIX}sgb_OBJECT", item_id).get('@id')
        media_data = get_media(item.get("o:id", ""))
        if media_data:
            for media in media_data:
                media_id = extract_property(media.get("dcterms:identifier", []), 10)
                media_class = specify_mediaclass(extract_property(media.get("dcterms:format", []), 9))
                if media_class:
                    mediadata_iri = get_resource_by_id(token, media_class, media_id).get('@id')
                    if mediadata_iri:
                        object = get_full_resource(token, urllib.parse.quote(mediadata_iri, safe=''))

                        if 'knora-api:lastModificationDate' in object:
                            dasch_date = object['knora-api:lastModificationDate']['@value']
                        else:
                            dasch_date = object['knora-api:creationDate']['@value']
                        if media['o:modified']['@value'] > dasch_date:
                            logging.info(f"{media_id}: media exists already, but it was modified. Update object ...")
                            modified_values = check_values(object, media, project_lists)
                            # print(modified_values)
                            for value in modified_values:
                                update_value(token, object,value["value"],value["field"],value["prop_type"],value["type"])
                        else:
                            logging.info(f"{media_id}: media exists already")
                    else:
                        if media.get("o:is_public", True):
                            logging.info(f"{media_id}: adding media to {media_class} ...")
                            object_location = media.get("o:original_url", "")
                            # TODO: zip file if it is not a dasch-valid format; geojson = TEXT?
                            internalFilename = upload_file_from_url(object_location,token)
                            if internalFilename:
                                media_payload = construct_payload(media, media_class, project_iri, project_lists, metadata_iri,internalFilename)
                                create_resource(media_payload, token)
                            else:
                                logging.error(f"{media_id}: could not create resource")
                                
                        else:
                            # TODO: create resource in StadtGeschichteBasel_v1:sgb_Media (without representation)???
                            logging.info(f"{media_id} is not public")
                else:
                    logging.error(f"{media_id}: could not create resource. Format is not supported: {extract_property(media.get("dcterms:format", []), 9)}")
        # break


if __name__ == "__main__":
    main()
