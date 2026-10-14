"""Each field offers its own kinds of content, and the writer is told what each kind must be."""
from app.services import content_types, generator, industries


def test_every_field_has_its_own_content_types():
    assert set(content_types.BY_INDUSTRY) == set(industries.INDUSTRIES)
    for field, ids in content_types.BY_INDUSTRY.items():
        assert len(ids) >= 6 and all(i in content_types.CATALOG for i in ids), field
        # the field's default content type is one of its own
        assert industries.INDUSTRIES[field]["content_type"] in ids, field
    assert "health_awareness" in content_types.for_industry("health")
    assert "destination" in content_types.for_industry("travel")
    assert "health_awareness" not in content_types.for_industry("travel")


def test_the_writer_gets_the_content_type_guidance():
    brand = generator.BrandContext(name="Clinic")
    prompt = generator.build_system_prompt(brand, {"language": "ar", "industry": "health", "content_type": "doctor_tip"})
    assert "Doctor's tip" in prompt and "practical advice" in prompt


def test_settings_options_list_types_per_field(client):
    opts = client.get("/api/settings").json()["options"]
    assert opts["content_type_labels"]["dish"]["ar"] == "طبق اليوم"
    assert "dish" in opts["content_types_by_industry"]["restaurants"]
    assert opts["image_sources"][0] == "article"


def test_company_profile_owns_language_and_dialect(client):
    before = client.get("/api/settings").json()["values"]["generation"]
    r = client.put("/api/settings/generation", json={**before, "language": "fr", "dialect": "gulf", "tone": "bold"})
    assert r.json()["language"] == before["language"] and r.json()["tone"] == "bold"
    client.put("/api/settings/generation", json={"tone": before["tone"]})
