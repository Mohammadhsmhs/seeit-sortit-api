import services.agent_tools as tools_mod

SAMPLE_YAML = """\
issue_types:
  - slug: pothole
    label: Pothole
    severity_hint: 3
  - slug: graffiti
    label: Graffiti
    severity_hint: 2
"""


def test_get_issue_taxonomy_returns_list(tmp_path, monkeypatch) -> None:
    yaml_file = tmp_path / "issue_types.yaml"
    yaml_file.write_text(SAMPLE_YAML)
    monkeypatch.setattr(tools_mod, "ISSUE_TYPES_PATH", str(yaml_file))

    result = tools_mod.get_issue_taxonomy.invoke({})

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["slug"] == "pothole"


def test_get_issue_taxonomy_contains_required_keys(tmp_path, monkeypatch) -> None:
    yaml_file = tmp_path / "issue_types.yaml"
    yaml_file.write_text(SAMPLE_YAML)
    monkeypatch.setattr(tools_mod, "ISSUE_TYPES_PATH", str(yaml_file))

    result = tools_mod.get_issue_taxonomy.invoke({})

    for item in result:
        assert "slug" in item
        assert "label" in item
        assert "severity_hint" in item


def test_get_issue_taxonomy_returns_empty_list_on_missing_file(monkeypatch) -> None:
    monkeypatch.setattr(tools_mod, "ISSUE_TYPES_PATH", "/nonexistent/path.yaml")

    result = tools_mod.get_issue_taxonomy.invoke({})

    assert result == []


def test_validate_location_returns_true_for_known_borough(tmp_path, monkeypatch) -> None:
    csv_file = tmp_path / "density.csv"
    csv_file.write_text("Location,Population_Density\nCamden,10500\nWestminster,12000\n")
    monkeypatch.setattr(tools_mod, "DENSITY_CSV_PATH", str(csv_file))
    tools_mod._load_locations.cache_clear()

    assert tools_mod.validate_location.invoke({"name": "Camden"}) is True


def test_validate_location_returns_false_for_unknown_location(tmp_path, monkeypatch) -> None:
    csv_file = tmp_path / "density.csv"
    csv_file.write_text("Location,Population_Density\nCamden,10500\n")
    monkeypatch.setattr(tools_mod, "DENSITY_CSV_PATH", str(csv_file))
    tools_mod._load_locations.cache_clear()

    assert tools_mod.validate_location.invoke({"name": "Narnia"}) is False


def test_validate_location_case_sensitive(tmp_path, monkeypatch) -> None:
    csv_file = tmp_path / "density.csv"
    csv_file.write_text("Location,Population_Density\nCamden,10500\n")
    monkeypatch.setattr(tools_mod, "DENSITY_CSV_PATH", str(csv_file))
    tools_mod._load_locations.cache_clear()

    assert tools_mod.validate_location.invoke({"name": "camden"}) is False


def test_validate_location_returns_false_on_missing_csv(monkeypatch) -> None:
    monkeypatch.setattr(tools_mod, "DENSITY_CSV_PATH", "/nonexistent/density.csv")
    tools_mod._load_locations.cache_clear()

    assert tools_mod.validate_location.invoke({"name": "Camden"}) is False
