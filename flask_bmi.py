from flask import Flask, render_template, request
import requests
from datetime import datetime
from Test import create_patient_resource, create_patient_observation_bundle, post_fhir_bundle

app = Flask(__name__)

FHIR_SERVER = "https://twcore.hapi.fhir.tw/fhir/"
LOINC_HEIGHT = "8302-2"
LOINC_WEIGHT = "29463-7"


# Route to handle form submission and create/upload FHIR bundle
@app.route('/create_bundle', methods=['POST'])
def create_bundle():
    given = request.form.get('given')
    family = request.form.get('family')
    gender = request.form.get('gender')
    birth_date = request.form.get('birth_date')
    height = request.form.get('height')
    weight = request.form.get('weight')

    # Create Patient resource
    patient_resource = create_patient_resource(given, family, gender, birth_date)
    # Create Bundle
    bundle = create_patient_observation_bundle(patient_resource, height, weight)
    # Upload Bundle
    response = post_fhir_bundle(bundle)
    if response.status_code in [200, 201]:
        msg = "FHIR Bundle uploaded successfully!"
    else:
        msg = f"Error uploading FHIR Bundle: {response.status_code} {response.text}"
    return render_template('index.html', result_message=msg)

def fetch_observations(loinc_code, count=10):
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
            patient_ref = obs.get("subject", {}).get("reference")
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

@app.route('/')
def home():
    return render_template('index.html')

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

