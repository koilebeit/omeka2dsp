import requests
import json 
import os
import urllib.parse

# Base API URL
host = "http://0.0.0.0:3333/"

save_directory = "../data" 
file_path = os.path.join(save_directory, "data_lists.json") 

# Replace these IRIs with actual values
project_iri = "http://rdfh.ch/projects/IbwoJlv8SEa6L13vXyCzMg"  

# URL encode the IRIs
encoded_project_iri = urllib.parse.quote(project_iri, safe='')


# Get lists
def get_lists():
    url = f"{host}/admin/lists/?projectIri={encoded_project_iri}"
    response = requests.get(url)
    if response.status_code == 200:
        print("Lists retrieved successfully!")
        print("Response:", response.json())
        with open(file_path, "w") as json_file:
            json.dump(response.json(), json_file, indent=4) 
    else:
        print(f"Failed to retrieve lists. Status code: {response.status_code}")
        print("Response:", response.text)


# Run the functions
get_lists()
