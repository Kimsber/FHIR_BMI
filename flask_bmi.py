from flask import Flask, render_template, request, redirect, url_for
import requests
from datetime import datetime
import uuid
import json

# Taiwan Core IG profile URLs
TAIWAN_PATIENT_PROFILE = "https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Patient-twcore"
TAIWAN_OBSERVATION_PROFILE = "https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Observation-vitalSigns-twcore"

app = Flask(__name__)

FHIR_SERVER = "https://twcore.hapi.fhir.tw/fhir/"
LOINC_HEIGHT = "8302-2"
LOINC_WEIGHT = "29463-7"
LOINC_BMI = "39156-5"
LONIC_VitalSigns = "85353-1"  # LONIC: Vital signs, weight, height, head circumference, oxygen saturation and BMI panel

# Function to create a Patient resource following the IG
def create_patient_resource(given, family, gender, birth_date):
    return {
        "resourceType": "Patient",
        "meta": {
            "profile": [TAIWAN_PATIENT_PROFILE]
        },
        "text": {
            "status": "generated",
            "div": f"<div xmlns=\"http://www.w3.org/1999/xhtml\">Patient: {family} {given}, Gender: {gender}, Birth: {birth_date}</div>"
        },
        "identifier": [
            {
                "system": "http://hospital.local/patient-id",
                "value": f"{family}-{given}-{birth_date}"
            }
        ],
        "name": [{
            "use": "official",
            "family": family,
            "given": [given]
        }],
        "gender": gender,
        "birthDate": birth_date
    }

# Function to create a single Observation resource (for height or weight)
def create_observation_code_value(code, display, value, unit):
    return {
        "code": {"coding": [{"system": "http://loinc.org",
                                 "code": code,
                                 "display": display}]},
        "valueQuantity": {"value": float(value), "unit": unit}
    }

# Function to create Observation resources for height and weight following the IG
def create_observation_resources(height, weight, height_unit, weight_unit, patient_ref):
    # Use correct LOINC display names
    vital_panel_display = "Vital signs, weight, height, head circumference, oxygen saturation and BMI panel"
    height_display = "Body height"
    weight_display = "Body weight"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Convert height to meters for BMI calculation
    try:
        if height_unit == "cm":
            height_m = float(height) / 100
            height_display_val = f"{height}cm"
        elif height_unit == "inch":
            height_m = float(height) * 0.0254
            height_display_val = f"{height}in"
        else:
            height_m = float(height)
            height_display_val = f"{height} {height_unit}"
    except Exception:
        height_m = None
        height_display_val = f"{height} {height_unit}"

    # Convert weight to kg for BMI calculation
    try:
        if weight_unit == "kg":
            weight_kg = float(weight)
            weight_display_val = f"{weight}kg"
        elif weight_unit == "pound":
            weight_kg = float(weight) * 0.45359237
            weight_display_val = f"{weight}lb"
        else:
            weight_kg = float(weight)
            weight_display_val = f"{weight} {weight_unit}"
    except Exception:
        weight_kg = None
        weight_display_val = f"{weight} {weight_unit}"

    # Calculate BMI
    try:
        bmi = weight_kg / (height_m ** 2) if height_m and weight_kg and height_m > 0 else None
    except Exception:
        bmi = None

    obs = {
        "resourceType": "Observation",
        "meta": {
            "profile": [TAIWAN_OBSERVATION_PROFILE]
        },
        "text": {
            "status": "generated",
            "div": f"<div xmlns=\"http://www.w3.org/1999/xhtml\">Observation: Height={height_display_val}, Weight={weight_display_val}, BMI={bmi:.2f}</div>" if bmi is not None else f"<div xmlns=\"http://www.w3.org/1999/xhtml\">Observation: Height={height_display_val}, Weight={weight_display_val}</div>"
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
             "display": vital_panel_display}
             ]
             },
        "subject": {"reference": patient_ref},
        "effectiveDateTime": now,
        "component": [
            create_observation_code_value(LOINC_HEIGHT, height_display, height, height_unit),
            create_observation_code_value(LOINC_WEIGHT, weight_display, weight, weight_unit)
        ]
    }
    if bmi is not None:
        obs["component"].append(create_observation_code_value("39156-5", "Body mass index (BMI)", bmi, "kg/m2"))
    return obs, bmi

# Function to create a FHIR transaction Bundle with Patient and Observations
def create_patient_observation_bundle(patient_resource, height, weight, height_unit, weight_unit):
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
    # Add Observation with its own fullUrl
    obs_uuid = str(uuid.uuid4())
    obs_fullUrl = f"urn:uuid:{obs_uuid}"
    obs_panel, bmi = create_observation_resources(height, weight, height_unit, weight_unit, patient_fullUrl)
    bundle["entry"].append({
        "fullUrl": obs_fullUrl,
        "resource": obs_panel,
        "request": {
            "method": "POST",
            "url": "Observation"
        }
    })
    return bundle, bmi

# Function to POST a FHIR bundle to the server
def post_fhir_bundle(bundle, server_url=FHIR_SERVER):
    """
    Posts a FHIR transaction bundle to the server.
    Returns the response object.
    """
    headers = {"Content-Type": "application/fhir+json"}
    response = requests.post(server_url, json=bundle, headers=headers)
    return response

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

# Route to handle form submission and create FHIR bundle
@app.route('/create_bundle', methods=['POST'])
def create_bundle():
    given = request.form.get('given')
    family = request.form.get('family')
    gender = request.form.get('Biological sex')
    birth_date = request.form.get('birth_date')
    height = request.form.get('height')
    weight = request.form.get('weight')
    height_unit = request.form.get('height_unit')
    weight_unit = request.form.get('weight_unit')
    # Validate required fields
    if not all([given, family, gender, birth_date, height, weight, height_unit, weight_unit]):
        return render_template('index.html', result_message="All fields are required.")
    try:
        height = float(height)
        weight = float(weight)
    except Exception:
        return render_template('index.html', result_message="Height and Weight must be numbers.")
    # Create Patient resource and bundle
    patient_resource = create_patient_resource(given, family, gender, birth_date)
    bundle, bmi = create_patient_observation_bundle(patient_resource, height, weight, height_unit, weight_unit)
    # Post bundle to FHIR server
    response = post_fhir_bundle(bundle)
    patient_url = None
    observation_url = None
    try:
        resp_json = response.json()
        if resp_json.get("resourceType") == "Bundle" and "entry" in resp_json:
            for entry in resp_json["entry"]:
                location = entry.get("response", {}).get("location", "")
                if location:
                    full_url = FHIR_SERVER + location.split('/_history')[0]
                    if "Patient" in location:
                        patient_url = full_url
                    elif "Observation" in location:
                        observation_url = full_url
    except Exception:
        patient_url = None
        observation_url = None

    # print(response.json())
    
    # Collect form variables
    result = {
        "patient_url": patient_url,
        "observation_url": observation_url,
        "given": given,
        "family": family,
        "gender": gender,
        "birth_date": birth_date,
        "height": height,
        "height_unit": height_unit,
        "weight": weight,
        "weight_unit": weight_unit,
        "bmi": bmi
    }
    return render_template('index.html', result=result)

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

# Fetch patient details for analysis
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

@app.route('/bmi')
def bmi():
    height_observations = fetch_observations(LOINC_HEIGHT, count=10)
    weight_observations = fetch_observations(LOINC_WEIGHT, count=10)
    num_pairs = min(len(height_observations), len(weight_observations))
    bmi_results = []
    for i in range(num_pairs):
        height_value, height_unit, patient_ref = height_observations[i]
        weight_value, weight_unit, _ = weight_observations[i]
        name, age, gender = fetch_patient(patient_ref)
        if height_value and weight_value:
            height_in_m = height_value / 100 if height_unit in ["cm", "centimeter", "centimeters"] else height_value
            bmi = weight_value / (height_in_m ** 2)
            if bmi < 18.5:
                status = "Underweight"
            elif 18.5 <= bmi < 24.9:
                status = "Normal"
            elif 25 <= bmi < 29.9:
                status = "Overweight"
            else:
                status = "Obese"
            bmi_str = f"{bmi:.2f}"
        else:
            bmi_str = "Unable to calculate"
            status = "N/A"
        bmi_results.append({
            'index': i+1,
            'name': name,
            'age': age,
            'gender': gender,
            'height': f"{height_value} {height_unit}",
            'weight': f"{weight_value} {weight_unit}",
            'bmi': bmi_str,
            'status': status
        })
    return render_template('bmi.html', bmi_results=bmi_results)

if __name__ == '__main__':
    app.run(debug=True)

