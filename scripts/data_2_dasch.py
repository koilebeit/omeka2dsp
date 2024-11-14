import urllib
from pathlib import Path
from typing import cast

import requests
import json

PROJECT_SHORT_CODE = "0856"
API_HOST = "http://0.0.0.0:3333"
INGEST_HOST = "http://0.0.0.0:3340"
DSP_USER = "root@example.com"
DSP_PWD = "test"

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

def get_ressource(token: str, object_class: str, identifier: str) -> json:
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
    ?metadata a StadtGeschichteBasel_v1:{object_class} .
    ?metadata StadtGeschichteBasel_v1:identifier ?identifierValue .
    ?identifierValue knora-api:valueAsString ?identifier .
    ?metadata StadtGeschichteBasel_v1:title ?title .
    FILTER(?identifier = "{identifier}")
}}
"""
    response = requests.post(endpoint, data=query.encode('utf-8'), headers=headers)
    if response.status_code == 200:
        print("Response:", response.json())
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
    return response.json()

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
    
    testfile = Path("../STORAGE_TEMP_DIR/0856/abb29212_Provinzen_West_Imperium_A.jpg")
    
    ##### WORKFLOW
    # get_project()
    # get list and list values TODO
    # for all sgb_OBJECTS (metadata)
        # if metadata exists already (check with function get_resource())
            # if values are different 
                # update values TODO
        # else
            # construct_payload() TODO
            # create_resource() 
    # for all sgb_MEDIA (medien)
        # if media exists already (check with function get_resource())
            # if values are different
                # update values TODO
        # else
            # get metadata_iri/parent_iri(get_ressource(token, "sgb_OBJECT", "abb123").get('@id'))
            # upload_file()
            # construct_payload() TODO
            # create_resource()

    ###### hints
    # DSP only versions values, not resource metadata (e.g. rdfs:label)
    # The Knora API doesn't directly support creating multiple resources in a single request, as it expects each resource to be created with its own POST request.
    # If you need to create two separate resources of type sgb_MEDIA_IMAGE in the Knora API, you would generally make two separate POST requests to the /v2/resources endpoint, 
    # each with its own payload dictionary representing one resource object.


    token = login(DSP_USER, DSP_PWD)
    project_iri = get_project()
    metadata_iri = get_ressource(token, "sgb_OBJECT", "abb123").get('@id') # metadata_iri = "http://rdfh.ch/0856/alDNmvZcQA-RLz8d3iQNMA"
    internal_filename_from_ingest = upload_file(testfile, token)
    create_resource(project_iri, internal_filename_from_ingest, token, metadata_iri)


if __name__ == "__main__":
    main()
