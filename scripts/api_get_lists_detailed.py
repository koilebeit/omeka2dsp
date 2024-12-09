import requests
import urllib.parse
import json

# Base API URL
host = "http://0.0.0.0:3333/v2"

json_file_path = "../data/data_lists.json"
output_file_path = "../data/data_lists_detail.json"

# Function to get a complete list by ID and return the JSON response
def get_complete_list(list_id):
    # URL encode the list IRI
    encoded_list_id = urllib.parse.quote(list_id, safe='')
    # Construct the API endpoint for this specific list ID
    url = f"{host}/lists/{encoded_list_id}"
    
    # Send the GET request
    response = requests.get(url)
    if response.status_code == 200:
        print(f"Complete list for {list_id} retrieved successfully!")
        return response.json() 
    else:
        print(f"Failed to retrieve complete list for {list_id}. Status code: {response.status_code}")
        print("Response:", response.text)
        return None

# Load the JSON data
try:
    with open(json_file_path, "r") as json_file:
        json_data = json.load(json_file)
        print("JSON data loaded successfully from file.")
except FileNotFoundError:
    print(f"Error: The file {json_file_path} was not found.")
    json_data = None

all_lists = []

# Check if the JSON data was loaded successfully
if json_data:
    # Iterate over each list item in the JSON data and retrieve its complete list
    for list_item in json_data["lists"]:
        list_id = list_item["id"]
        list_data = get_complete_list(list_id)  
        if list_data is not None:
            all_lists.append(list_data)

# Save all collected data to the output file
if all_lists:
    with open(output_file_path, "w") as output_file:
        json.dump(all_lists, output_file, indent=4)  
    print(f"All list data saved successfully to {output_file_path}.")
else:
    print("No data to save.")
