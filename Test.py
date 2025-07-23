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