from datetime import datetime
import requests
import uuid

# Taiwan Core IG profile URLs
TAIWAN_PATIENT_PROFILE = "https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition-Patient-twcore.html"
TAIWAN_OBSERVATION_PROFILE = "https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition-Observation-vitalSigns-twcore.html"

# FHIR server endpoint (Taiwan Core)
FHIR_SERVER = "https://twcore.hapi.fhir.tw/fhir/"

# LOINC codes for height and weight
LOINC_HEIGHT = "8302-2"
LOINC_WEIGHT = "29463-7"
LONIC_VitalSigns = "85353-1"  # LONIC: Vital signs, weight, height, head circumference, oxygen saturation and BMI panel

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

# Function to create a single Observation resource (for height or weight)
def create_observation_code_value(code, display, value, unit):
    return {
        "code": {"coding": [{"system": "http://loinc.org", 
                             "code": code, 
                             "display": display}]},
        "valueQuantity": {"value": float(value), "unit": unit}
        # Add other required fields/extensions per IG if needed
    }

# Function to create Observation resources for height and weight following the IG
def create_observation_resources(height, weight, patient_ref):
    return {
        "resourceType": "Observation",
        "meta": {
            "profile": [TAIWAN_OBSERVATION_PROFILE]
        },
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs"
                    }
                ]
            }
        ],
        "code": {"coding": [
            {"system": "http://loinc.org", 
             "code": LONIC_VitalSigns, 
             "display": "Vital signs panel"}
             ]
             },
        "subject": {"reference": patient_ref},
        "effectiveDateTime": datetime.now().isoformat(),
        "component": [
            create_observation_code_value(LOINC_HEIGHT, "Height", height, "cm"),
            create_observation_code_value(LOINC_WEIGHT, "Weight", weight, "kg")
        ]
    }

# Function to create a FHIR transaction Bundle with Patient and Observations
def create_patient_observation_bundle(patient_resource, height, weight):
    """
    Create a transaction Bundle with Patient and Observations (height, weight).
    The patient_ref for Observations is a generated UUID fullUrl.
    """
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": []
    }
    # Generate a unique UUID for the patient fullUrl
    patient_uuid = str(uuid.uuid4())
    patient_fullUrl = f"urn:uuid:{patient_uuid}"
    # Add Patient as a POST entry with fullUrl
    bundle["entry"].append({
        "fullUrl": patient_fullUrl,
        "resource": patient_resource,
        "request": {
            "method": "POST",
            "url": "Patient"
        }
    })
    # Create a single panel Observation using the patient_fullUrl as patient_ref
    obs_panel = create_observation_resources(height, weight, patient_fullUrl)
    bundle["entry"].append({
        "resource": obs_panel,
        "request": {
            "method": "POST",
            "url": "Observation"
        }
    })
    return bundle

# Function to POST a FHIR bundle to the server
def post_fhir_bundle(bundle, server_url=FHIR_SERVER):
    """
    Posts a FHIR transaction bundle to the server.
    Returns the response object.
    """
    headers = {"Content-Type": "application/fhir+json"}
    response = requests.post(server_url, json=bundle, headers=headers)
    return response

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

# Main function to fetch height and weight observations, pair them, and calculate BMI
if __name__ == "__main__":
    # Fetch all available height and weight observations (set a high count, e.g., 100)
    height_observations = fetch_observations(LOINC_HEIGHT)
    weight_observations = fetch_observations(LOINC_WEIGHT)

    # Pair height and weight observations by index and calculate BMI for each pair
    print("Height and Weight Observations with BMI Calculation:")
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

