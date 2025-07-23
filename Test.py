# Function to create a FHIR transaction Bundle with Patient and Observations
def create_patient_observation_bundle(patient_resource, obs_resources):
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": []
    }
    # Add Patient as a POST entry
    bundle["entry"].append({
        "resource": patient_resource,
        "request": {
            "method": "POST",
            "url": "Patient"
        }
    })
    # Add Observations as POST entries, referencing the patient via a temporary fullUrl
    patient_fullUrl = "urn:uuid:patient1"
    bundle["entry"][0]["fullUrl"] = patient_fullUrl
    for obs in obs_resources:
        obs = obs.copy()
        obs["subject"] = {"reference": patient_fullUrl}
        bundle["entry"].append({
            "resource": obs,
            "request": {
                "method": "POST",
                "url": "Observation"
            }
        })
    return bundle
# Taiwan Core IG profile URLs
TAIWAN_PATIENT_PROFILE = "https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Patient-twcore"
TAIWAN_OBSERVATION_PROFILE = "https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Observation-twcore"

# Function to create a Patient resource following the IG
def create_patient_resource(given, family, gender, birth_date):
    return {
        "resourceType": "Patient",
        "meta": {
            "profile": [TAIWAN_PATIENT_PROFILE]
        },
        "name": [{
            "use": "official",
            "family": family,
            "given": [given]
        }],
        "gender": gender,
        "birthDate": birth_date
        # Add other required fields/extensions per IG if needed
    }

# Function to create Observation resources for height and weight following the IG
def create_observation_resources(height, weight, patient_ref):
    return [
        {
            "resourceType": "Observation",
            "meta": {
                "profile": [TAIWAN_OBSERVATION_PROFILE]
            },
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "8302-2", "display": "Height"}]},
            "subject": {"reference": patient_ref},
            "valueQuantity": {"value": float(height), "unit": "cm"}
            # Add other required fields/extensions per IG if needed
        },
        {
            "resourceType": "Observation",
            "meta": {
                "profile": [TAIWAN_OBSERVATION_PROFILE]
            },
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7", "display": "Weight"}]},
            "subject": {"reference": patient_ref},
            "valueQuantity": {"value": float(weight), "unit": "kg"}
            # Add other required fields/extensions per IG if needed
        }
    ]

import requests
from datetime import datetime

# FHIR server endpoint (Taiwan Core)
FHIR_SERVER = "https://twcore.hapi.fhir.tw/fhir/"

# LOINC codes for height and weight
LOINC_HEIGHT = "8302-2"
LOINC_WEIGHT = "29463-7"
LONIC_Main = "85353-1"  # LONIC: Vital signs, weight, height, head circumference, oxygen saturation and BMI panel

# Fetch the latest observation for a given LOINC code from the FHIR server
def fetch_observations(loinc_code, count=50):
    url = str(FHIR_SERVER + f"Observation?code=http://loinc.org|{loinc_code}&_sort=-date&_count={count}")
    results = []
    while url:
        response = requests.get(url)
        if response.status_code != 200:
            break
        bundle = response.json()
        entries = bundle.get("entry", [])
        for entry in entries:
            obs = entry["resource"]
            value = obs.get("valueQuantity", {}).get("value")
            unit = obs.get("valueQuantity", {}).get("unit")
            patient_ref = obs.get("subject", {}).get("reference") #取得對照病人名稱
            results.append((value, unit, patient_ref))
        # Find the next page link
        next_url = None
        for link in bundle.get("link", []):
            if link.get("relation") == "next":
                next_url = link.get("url")
                break
        url = next_url
    return results


def fetch_patient(patient_ref):
    if not patient_ref:
        return None, None, None
    url = FHIR_SERVER + patient_ref
    response = requests.get(url)
    if response.status_code != 200:
        return None, None, None
    patient = response.json()
    name = ""
    if "name" in patient and patient["name"]:
        name_parts = patient["name"][0]
        name = " ".join(name_parts.get("given", [])) + " " + name_parts.get("family", "")
    gender = patient.get("gender", "")
    birth_date = patient.get("birthDate", "")
    age = ""
    if birth_date:
        try:
            birth = datetime.strptime(birth_date, "%Y-%m-%d")
            today = datetime.today()
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        except:
            age = ""
    return name.strip(), age, gender


# Fetch all available height and weight observations (set a high count, e.g., 100)
height_observations = fetch_observations(LOINC_HEIGHT)
weight_observations = fetch_observations(LOINC_WEIGHT)

# Pair height and weight observations by index and calculate BMI for each pair
num_pairs = min(len(height_observations), len(weight_observations))
print(f"{'Name':<20} {'Age':<5} {'Gender':<8} {'Height':<10} {'Weight':<10} {'BMI':<6}")
for i in range(num_pairs):
    height_value, height_unit, patient_ref = height_observations[i]
    weight_value, weight_unit, _ = weight_observations[i]
    name, age, gender = fetch_patient(patient_ref)
    if height_value and weight_value:
        height_in_m = height_value / 100 if height_unit in ["cm", "centimeter", "centimeters"] else height_value
        bmi = weight_value / (height_in_m ** 2)
        bmi_str = f"{bmi:.2f}"
    else:
        bmi_str = "N/A"
    print(f"{name:<20} {age!s:<5} {gender:<8} {height_value!s:<10} {weight_value!s:<10} {bmi_str:<6}")

# Function to upload (POST) or update (PUT) a FHIR resource to the server
def upload_fhir_resource(resource, resource_type=None, resource_id=None, server_url=FHIR_SERVER):
    """
    Uploads (POST) or updates (PUT) a FHIR resource to the server.
    If resource is a Bundle, uploads as a transaction.
    If resource_id is provided, uses PUT to update; otherwise, uses POST to create.
    Returns the response object.
    """
    headers = {"Content-Type": "application/fhir+json"}
    if resource.get("resourceType") == "Bundle":
        url = f"{server_url}"
        response = requests.post(url, json=resource, headers=headers)
        return response
    if resource_type is None:
        resource_type = resource.get("resourceType")
    if resource_id:
        # Update (PUT)
        url = f"{server_url}{resource_type}/{resource_id}"
        response = requests.put(url, json=resource, headers=headers)
    else:
        # Create (POST)
        url = f"{server_url}{resource_type}"
        response = requests.post(url, json=resource, headers=headers)
    return response
