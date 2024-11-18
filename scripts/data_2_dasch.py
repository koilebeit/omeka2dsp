import urllib
from pathlib import Path
from typing import cast

import logging
import os

import requests
import json

PROJECT_SHORT_CODE = os.getenv("PROJECT_SHORT_CODE", "0856")
API_HOST = os.getenv("API_HOST", "http://0.0.0.0:3333")
INGEST_HOST = os.getenv("INGEST_HOST", "http://0.0.0.0:3340")
DSP_USER = os.getenv("DSP_USER", "root@example.com")
DSP_PWD = os.getenv("DSP_PWD", "test")

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

def login(email: str, password: str) -> str:
    endpoint = f"{API_HOST}/v2/authentication"
    response = requests.post(endpoint, json={"email": email, "password": password}, timeout=10)
    print("Login successful")
    return cast(str, response.json()["token"])

def get_project():
    endpoint = f"{API_HOST}/admin/projects/shortcode/{PROJECT_SHORT_CODE}"
    response = requests.get(endpoint)
    if response.status_code == 200:
        print("project Iri:", cast(str, response.json()["project"]["id"]))
    else:
        print(f"Failed to retrieve project. Status code: {response.status_code}")
        print("Response:", response.text)
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
                print(f"Complete list for {list_id} retrieved successfully!")
            else:
                print(f"Failed to retrieve complete list for {list_id}. Status code: {response.status_code}")
                print("Response:", response.text)

    else:
        print(f"Failed to retrieve lists. Status code: {response.status_code}")
        print("Response:", response.text)
    return all_lists

def get_ressource(token: str, object_class: str, identifier: str) -> dict:
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
        print("Resource:", response.json())
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return {}

def construct_payload():
    # TODO:
    # - set project_IRI
    # - set correct listvalue_IRIs
    # - set metadata_IRI (only if Media)
    # - set internalFilename (only if Media)

    return ""

def upload_file(filepath: Path, token: str) -> str:
    # http://0.0.0.0:3340/docs/#/assets/postProjectsShortcodeAssetsIngestFilename
    filename = urllib.parse.quote(filepath.name)
    endpoint = f"{INGEST_HOST}/projects/{PROJECT_SHORT_CODE}/assets/ingest/{filename}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }
    response = requests.post(endpoint, data=filepath.read_bytes(), headers=headers, timeout=10)
    if response.status_code == 200:
        print("File uploaded")
    else:
        print(f"File upload failed: {response.status_code}: {response.text}")
    return cast(str, response.json()["internalFilename"])

# TODO: construct payload in another function
def create_resource(proj_iri: str, internal_filename_from_ingest: str, token: str, metadata_iri: str) -> None:
    # https://docs.dasch.swiss/latest/DSP-API/03-endpoints/api-v2/editing-resources/#creating-a-resource
    resources_endpoint = f"{API_HOST}/v2/resources"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Asset-Ingested": "true",
    }
    payload = {
        "@type": "StadtGeschichteBasel_v1:sgb_MEDIA_IMAGE",
        "knora-api:attachedToProject": {
            "@id": proj_iri,
        },
        "knora-api:hasStillImageFileValue": {
            "@type": "knora-api:StillImageFileValue",
            "knora-api:fileValueHasFilename": internal_filename_from_ingest,
        },
        "StadtGeschichteBasel_v1:identifier": {
            "knora-api:valueAsString": "m30m123849",
            "@type": "knora-api:TextValue"
        },
        "StadtGeschichteBasel_v1:title": {
            "knora-api:valueAsString": " Mauerreste der villa rustica (Riehen-Landauerhof), 2.–3. Jh. n. Chr.",
            "@type": "knora-api:TextValue"
        },
        "StadtGeschichteBasel_v1:partOf_MetadataValue" : {
            "@type": "knora-api:LinkValue",
            "knora-api:linkValueHasTargetIri" : {
                "@id" : metadata_iri,
            }
        },
        "rdfs:label": "asdf",
        "@context": {
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "knora-api": "http://api.knora.org/ontology/knora-api/v2#",
            "StadtGeschichteBasel_v1": "http://0.0.0.0:3333/ontology/0856/StadtGeschichteBasel_v1/v2#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        },
    }
    response = requests.post(resources_endpoint, json=payload, headers=headers, timeout=10)
    if response.status_code == 200:
        print("Resource created")
    else:
        print(f"Resource creation failed: {response.status_code}: {response.text}")


def main() -> None:
    # Temporary test files
    testfile = Path("../data/media_files/f1170f2dd7b49feb73a241f2bda2889d3659460b.tif")
    test_object = Path("../data/example_payload_OBJEKT.json")
    test_media = Path("../data/example_payload_MEDIA.json")
    with open(test_object, "r") as json_file:
        object_item = json.load(json_file)
    with open(test_media, "r") as json_file:
        media_item = json.load(json_file)

    ##### WORKFLOW
    # get_project()
    token = login(DSP_USER, DSP_PWD)
    project_iri = get_project()
    # get list and list values
    project_lists = get_lists(project_iri)

# for all sgb_OBJECTS (metadata)
    metadata_iri = get_ressource(token, object_item["@type"], object_item["StadtGeschichteBasel_v1:identifier"]["knora-api:valueAsString"]).get('@id')
    # if metadata exists already (check with function get_resource())
    if metadata_iri:
        print("object_item exists already")
            # if values are different 
               # update values TODO
    else:
        print("you can add the object_item to dasch")
        # construct_payload() TODO
        # create_resource(project_iri, internal_filename_from_ingest, token, metadata_iri)

# for all sgb_MEDIA (medien)
    # if media exists already (check with function get_resource())
    media_iri = get_ressource(token, media_item["@type"], media_item["StadtGeschichteBasel_v1:identifier"]["knora-api:valueAsString"]).get('@id')
        # if values are different
    if media_iri:
        print("media_item exists already")
            # update values TODO
    # else
    else:
        print("you can add the media_item to dasch")
        # get metadata_iri/parent_iri(get_ressource(token, "sgb_OBJECT", "abb123").get('@id'))
        # -- upload_file()
        # internal_filename_from_ingest = upload_file(testfile, token)
        # construct_payload() TODO
        # create_resource(project_iri, internal_filename_from_ingest, token, metadata_iri)




if __name__ == "__main__":
    main()


    ###### hints
    # DSP only versions values, not resource metadata (e.g. rdfs:label)
    # The Knora API doesn't directly support creating multiple resources in a single request, as it expects each resource to be created with its own POST request.
    # If you need to create two separate resources of type sgb_MEDIA_IMAGE in the Knora API, you would generally make two separate POST requests to the /v2/resources endpoint, 
    # each with its own payload dictionary representing one resource object.