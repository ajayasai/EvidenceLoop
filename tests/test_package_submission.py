"""Archive boundary checks use only temporary files and fictional credentials."""
import hashlib
import json
import zipfile

import pytest

from scripts import package_submission as package


@pytest.fixture
def source(tmp_path,monkeypatch):
    monkeypatch.setattr(package,"ROOT_FILES",("README.md",".env.example"))
    monkeypatch.setattr(package,"SOURCE_TREES",{"services":{".py"}})
    monkeypatch.setattr(package,"SPONSOR_FILES",())
    monkeypatch.setattr(package,"FROZEN_METADATA",())
    monkeypatch.setattr(package,"RESULT_ROOTS",())
    (tmp_path/"README.md").write_text("Fictional source bundle test.",encoding="utf-8")
    (tmp_path/".env.example").write_text("MODEL_API_KEY=\n",encoding="utf-8")
    (tmp_path/".env.ai").write_text("MODEL_API_KEY=fictional-private-token-123456\n",encoding="utf-8")
    (tmp_path/"services").mkdir()
    (tmp_path/"services/main.py").write_text("value = 1\n",encoding="utf-8")
    (tmp_path/"services/__pycache__").mkdir()
    (tmp_path/"services/__pycache__/private.py").write_text("excluded = True\n",encoding="utf-8")
    return tmp_path


def test_bundle_is_reproducible_and_verifies_only_allowlisted_bytes(source):
    output=source/"artifacts/source"
    first=package.build(source,output)
    archive=(output/first["archive_file"]).read_bytes()
    second=package.build(source,output)
    assert (output/first["archive_file"]).read_bytes()==archive
    assert first["archive_sha256"]==second["archive_sha256"]==hashlib.sha256(archive).hexdigest()
    with zipfile.ZipFile(output/first["archive_file"]) as bundle:
        assert set(bundle.namelist())=={"EvidenceLoop/README.md","EvidenceLoop/.env.example",
            "EvidenceLoop/services/main.py","EvidenceLoop/BUNDLE_MANIFEST.json"}
        manifest=json.loads(bundle.read("EvidenceLoop/BUNDLE_MANIFEST.json"))
        assert manifest["file_count"]==3
        for record in manifest["files"]:
            data=bundle.read("EvidenceLoop/"+record["path"])
            assert len(data)==record["bytes"] and hashlib.sha256(data).hexdigest()==record["sha256"]


def test_known_private_credential_aborts_without_creating_an_archive(source):
    (source/"README.md").write_text("fictional-private-token-123456",encoding="utf-8")
    with pytest.raises(package.BundleError) as error:
        package.build(source,source/"artifacts/source")
    assert "README.md" in str(error.value)
    assert "fictional-private-token" not in str(error.value)
    assert not (source/"artifacts/source/EvidenceLoop-source.zip").exists()


def test_source_mutation_during_packaging_aborts_publication(source,monkeypatch):
    original=zipfile.ZipFile.writestr
    def mutate_after_write(self,*args,**kwargs):
        result=original(self,*args,**kwargs)
        (source/"README.md").write_text("Concurrent source edit.",encoding="utf-8")
        return result
    monkeypatch.setattr(zipfile.ZipFile,"writestr",mutate_after_write)
    with pytest.raises(package.BundleError,match="Source changed during packaging"):
        package.build(source,source/"artifacts/source")
    assert not (source/"artifacts/source/EvidenceLoop-source.zip").exists()
    assert not list((source/"artifacts/source").glob("*.tmp-*"))
