import requests
import json 
import os

# Base API URL
PROJECT_SHORT_CODE = os.getenv("PROJECT_SHORT_CODE")
API_HOST = os.getenv("API_HOST") 

save_directory = "../data" 
file_path = os.path.join(save_directory, "project_data.json")  

# Get a project
def get_project():
    url = f"{API_HOST}/admin/projects/shortcode/{PROJECT_SHORT_CODE}"
    response = requests.get(url)

    if response.status_code == 200:
        print("Response:", response.json())
        with open(file_path, "w") as json_file:
            json.dump(response.json(), json_file, indent=4) 

    else:
        print(f"Failed to retrieve project. Status code: {response.status_code}")
        print("Response:", response.text)


# Run the functions
get_project()

