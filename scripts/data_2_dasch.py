import urllib
from pathlib import Path
from typing import cast
import tempfile

import logging
import os

import requests
import json

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

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

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


def get_resource(token: str, object_class: str, identifier: str) -> dict:
    endpoint = f"{API_HOST}/v2/searchextended"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/sparql-query; charset=utf-8"
    }
    query = f"""
        PREFIX knora-api: <http://api.knora.org/ontology/knora-api/v2#>
        PREFIX StadtGeschichteBasel_v1: <http://0.0.0.0:3333/ontology/0856/StadtGeschichteBasel_v1/v2#>
        CONSTRUCT {{
            ?metadata knora-api:isMainResource true .
            ?metadata StadtGeschichteBasel_v1:identifier ?identifierValue .
            ?metadata StadtGeschichteBasel_v1:title ?title .
        }} WHERE {{
            ?metadata a {object_class} .
            ?metadata StadtGeschichteBasel_v1:identifier ?identifierValue .
            ?identifierValue knora-api:valueAsString ?identifier .
            ?metadata StadtGeschichteBasel_v1:title ?title .
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

def update_value():
    logging.info("TODO: update object with dasch api")

def arrays_equal(array1, array2):
    if len(array1) != len(array2):
        return False
    return set(array1) == set(array2)

def check_values(dasch_item, omeka_item, lists):
    # TODO: function not complete yet
    dasch_isPartOf = [entry.get("knora-api:valueAsString") for entry in (dasch_item.get("StadtGeschichteBasel_v1:isPartOf", []) 
                                                                            if isinstance(dasch_item.get("StadtGeschichteBasel_v1:isPartOf"), list) 
                                                                            else [dasch_item.get("StadtGeschichteBasel_v1:isPartOf")]) if isinstance(entry, dict)]
    omeka_isPartOf = [entry['@value'] for entry in omeka_item['dcterms:isPartOf']]
    dasch_subjects = [
        entry["knora-api:listValueAsListNode"]["@id"]
        for entry in (dasch_item.get("StadtGeschichteBasel_v1:subject", [])
                    if isinstance(dasch_item.get("StadtGeschichteBasel_v1:subject"), list)
                    else [dasch_item.get("StadtGeschichteBasel_v1:subject")]
                    if isinstance(dasch_item.get("StadtGeschichteBasel_v1:subject"), dict)
                    else [])
        if isinstance(entry, dict) and "knora-api:listValueAsListNode" in entry
    ]
    omeka_subjects = [
        result for entry in omeka_item.get('dcterms:subject', [])
        if (result := update_value_with_listvalueiri(entry['@value'], "Thema", lists)) is not None
    ]
    if dasch_item["StadtGeschichteBasel_v1:title"]["knora-api:valueAsString"] != omeka_item['dcterms:title'][0]['@value']:
        update_value()
    if dasch_item["StadtGeschichteBasel_v1:description"]["knora-api:valueAsString"] != omeka_item['dcterms:description'][0]['@value']:
        update_value()
    if dasch_item["StadtGeschichteBasel_v1:language"]["knora-api:valueAsString"] != omeka_item['dcterms:language'][0]['@value']:
        update_value()
    if dasch_item["StadtGeschichteBasel_v1:temporal"]["knora-api:listValueAsListNode"]["@id"] != update_value_with_listvalueiri(omeka_item['dcterms:temporal'][0]['@value'], "Era", lists):
        update_value()
    if not arrays_equal(dasch_isPartOf,omeka_isPartOf):
        print(dasch_isPartOf)   
        print(omeka_isPartOf)
    if not arrays_equal(dasch_subjects,omeka_subjects):
        print(dasch_subjects)   
        print(omeka_subjects) 



def update_value_with_listvalueiri(value, list_label, lists):
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
        "StadtGeschichteBasel_v1:identifier": {
            "knora-api:valueAsString": extract_property(item.get("dcterms:identifier", []), 10),
            "@type": "knora-api:TextValue"
        },
        "StadtGeschichteBasel_v1:title": {
            "knora-api:valueAsString": extract_property(item.get("dcterms:title", []), 1),
            "@type": "knora-api:TextValue"
        }
    }
    payload["StadtGeschichteBasel_v1:description"] = {
        "knora-api:valueAsString": extract_property(item.get("dcterms:description", []), 4),
        "@type": "knora-api:TextValue"
    }
    if 'dcterms:subject' in item:
        subjects = []
        for data in extract_combined_values(item.get("dcterms:subject", [])):
            subject = update_value_with_listvalueiri(data, "Thema", lists)
            if subject:
                subjects.append({
                "@type": "knora-api:ListValue",
                "knora-api:listValueAsListNode": {
                    "@id": subject
            }})
        payload["StadtGeschichteBasel_v1:subject"] = subjects
    if 'dcterms:temporal' in item:
        temporal = update_value_with_listvalueiri(extract_property(item.get("dcterms:temporal", []), 41), "Era", lists)
        if temporal:
            payload["StadtGeschichteBasel_v1:temporal"] = {
                "@type": "knora-api:ListValue",
                "knora-api:listValueAsListNode": {
                    "@id": temporal
                }
            }
    if 'dcterms:language' in item:
        payload["StadtGeschichteBasel_v1:language"] =  {
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
        payload["StadtGeschichteBasel_v1:isPartOf"] = isPartOf
         
    # Handle MEDIA type-specific fields
    if type == "StadtGeschichteBasel_v1:sgb_MEDIA_IMAGE":
        payload["knora-api:hasStillImageFileValue"] =  {
            "@type": "knora-api:StillImageFileValue",
            "knora-api:fileValueHasFilename": internalMediaFilename
        }
    if type == "StadtGeschichteBasel_v1:sgb_MEDIA_ARCHIV":
        payload["knora-api:hasArchiveFileValue"] =  {
            "@type": "knora-api:ArchiveFileValue",
            "knora-api:fileValueHasFilename": internalMediaFilename
        }
    if type == "StadtGeschichteBasel_v1:sgb_MEDIA_DOCUMENT":
        payload["knora-api:hasDocumentFileValue"] =  {
            "@type": "knora-api:DocumentFileValue",
            "knora-api:fileValueHasFilename": internalMediaFilename
        }
    if type == "StadtGeschichteBasel_v1:sgb_MEDIA_TEXT":
        payload["knora-api:hasTextFileValue"] =  {
            "@type": "knora-api:TextFileValue",
            "knora-api:fileValueHasFilename": internalMediaFilename
        }
    if type.startswith("StadtGeschichteBasel_v1:sgb_MEDIA"):

        payload["StadtGeschichteBasel_v1:partOf_MetadataValue"] = {
            "@type": "knora-api:LinkValue",
            "knora-api:linkValueHasTargetIri": {
                "@id": parent_iri
            }
        }
        if 'dcterms:date' in item:
            payload["StadtGeschichteBasel_v1:date"] = {
                "knora-api:valueAsString": extract_property(item.get("dcterms:date", []), 7),
                "@type": "knora-api:TextValue"
            }       
        mediatype = update_value_with_listvalueiri(extract_property(item.get("dcterms:type", []), 8, only_label=True), "DCMI Type Vocabulary", lists)
        if mediatype:
            payload["StadtGeschichteBasel_v1:type"] = {
                "@type": "knora-api:ListValue",
                "knora-api:listValueAsListNode": {
                    "@id": mediatype
                }
            }
        format = update_value_with_listvalueiri(extract_property(item.get("dcterms:format", []), 9), "Internet Media Type", lists)
        if format:
            payload["StadtGeschichteBasel_v1:format"] = {
                "@type": "knora-api:ListValue",
                "knora-api:listValueAsListNode": {
                    "@id": format
                }
            }
        if 'dcterms:extent' in item:
            payload["StadtGeschichteBasel_v1:extent"] = {
                "knora-api:valueAsString": extract_property(item.get("dcterms:extent", []), 25),
                "@type": "knora-api:TextValue"
            }
        if 'dcterms:rights' in item:
            payload["StadtGeschichteBasel_v1:rights"] = {
                "knora-api:valueAsString": extract_property(item.get("dcterms:rights", []), 15),
                "@type": "knora-api:TextValue"
            }
        if 'dcterms:license' in item:
            payload["StadtGeschichteBasel_v1:license"] = {
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
            payload["StadtGeschichteBasel_v1:creator"] = creators
        if 'dcterms:publisher' in item:
            publishers = []
            for data in extract_combined_values(item.get("dcterms:publisher", [])): 
                publishers.append({
                    "knora-api:valueAsString": data,
                    "@type": "knora-api:TextValue"
                })
            payload["StadtGeschichteBasel_v1:publisher"] = publishers
        if 'dcterms:source' in item:
            sources = []
            for data in extract_combined_values(item.get("dcterms:source", [])): 
                sources.append({
                    "knora-api:valueAsString": data,
                    "@type": "knora-api:TextValue"
                })
            payload["StadtGeschichteBasel_v1:source"] = sources
        if 'dcterms:relation' in item:
            relations = []
            for data in extract_combined_values(item.get("dcterms:relation", [])): 
                relations.append({
                    "knora-api:valueAsString": data,
                    "@type": "knora-api:TextValue"
                })
            payload["StadtGeschichteBasel_v1:relation"] = relations

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
    except requests.exceptions.RequestException as err:
        logging.error(f"File upload error: {err}")
        raise   
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
        logging.info(f"{payload["StadtGeschichteBasel_v1:identifier"]["knora-api:valueAsString"]}: resource created on DaSCH")
    else:
        logging.error(f"{payload["StadtGeschichteBasel_v1:identifier"]["knora-api:valueAsString"]}: resource creation failed: {response.status_code}: {response.text}")
        logging.error(payload)


def specify_mediaclass(media_type: str) -> str:
    valid_images_types = {"image/tiff", "image/jpg", "image/jpeg", "image/png", "image/gif"}
    valid_text_types = {"text/csv", "text/markdown", "text/plain", "application/json"}
    valid_doc_types = {"application/pdf"}
    if media_type in valid_images_types:
        return "StadtGeschichteBasel_v1:sgb_MEDIA_IMAGE"
    if media_type in valid_text_types:
        return "StadtGeschichteBasel_v1:sgb_MEDIA_TEXT"
    if media_type in valid_doc_types:
        return "StadtGeschichteBasel_v1:sgb_MEDIA_DOCUMENT"
    # TODO: StadtGeschichteBasel_v1:sgb_MEDIA_ARCHIV (e.g. for geojson)
    else:
        return None
    

def main() -> None:
    # Temporary test files
    """     testfile = Path("../data/media_files/f1170f2dd7b49feb73a241f2bda2889d3659460b.tif")
    test_object = Path("../data/example_payload_OBJEKT_unprocessed.json")
    test_media = Path("../data/example_payload_MEDIA_unprocessed.json")
    with open(test_object, "r") as json_file:
        object_item = json.load(json_file)
    with open(test_media, "r") as json_file:
        media_item = json.load(json_file) """

    # Fetch item data
    items_data = get_items_from_collection(ITEM_SET_ID)
    # get_project()
    token = login(DSP_USER, DSP_PWD)
    project_iri = get_project()
    # get list and list values
    project_lists = get_lists(project_iri)

    for item in items_data:
        item_id = extract_property(item.get("dcterms:identifier", []), 10)
        metadata_iri = get_resource(token, "StadtGeschichteBasel_v1:sgb_OBJECT", item_id).get('@id')
        if metadata_iri:
            logging.info(f"{item_id}: object exists already")
            object = get_full_resource(token, urllib.parse.quote(metadata_iri, safe=''))
            if 'knora-api:lastModificationDate' in object:
                dasch_date = object['knora-api:lastModificationDate']['@value']
            else:
                dasch_date = object['knora-api:creationDate']['@value']
            if item['o:modified']['@value'] > dasch_date:
                logging.info("TODO: update item")
                check_values(object, item, project_lists)
                # TODO if values are different 
                # TODO update values 
            else:
                logging.info(f"{item_id}: no update necessary")
        else:
            payload = construct_payload(item, "StadtGeschichteBasel_v1:sgb_OBJECT", project_iri, project_lists,"","")
            create_resource(payload, token)
            metadata_iri = get_resource(token, "StadtGeschichteBasel_v1:sgb_OBJECT", item_id).get('@id')
        media_data = get_media(item.get("o:id", ""))
        if media_data:
            for media in media_data:
                media_id = extract_property(media.get("dcterms:identifier", []), 10)
                media_class = specify_mediaclass(extract_property(media.get("dcterms:format", []), 9))
                if media_class:
                    mediadata_iri = get_resource(token, media_class, media_id).get('@id')
                    if mediadata_iri:
                        logging.info(f"{media_id}: media exists already")
                        # TODO check if update is necessary
                    else:
                        if media.get("o:is_public", True):
                            logging.info(f"{media_id}: adding media to {media_class} ...")
                            object_location = media.get("o:original_url", "")
                            # TODO: zip file if it is not a dasch-valid format; geojson = TEXT?
                            internalFilename = upload_file_from_url(object_location,token)
                            if internalFilename:
                                print(item_id)
                                print(metadata_iri)
                                media_payload = construct_payload(media, media_class, project_iri, project_lists, metadata_iri,internalFilename)
                                create_resource(media_payload, token)
                            else:
                                break
                        else:
                            # TODO: create resource in StadtGeschichteBasel_v1:sgb_Media (without representation)???
                            logging.info(f"{media_id} is not public")
            
        # break


if __name__ == "__main__":
    main()
