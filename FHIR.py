from fhir.resources.organization import Organization
from fhir.resources.address import Address

data = {
    "id": "f001",
    "active": True,
    "name": "Acme Corporation",
    "address": [{"country": "Switzerland"}],
}

org = Organization.model_construct(**data)
org.get_resource_type() == "Organization"
