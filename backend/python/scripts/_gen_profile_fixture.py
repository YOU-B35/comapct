from pathlib import Path

from app.browser.profile_bundle import pack_profile_essentials

root = Path(__file__).resolve().parents[1]
profile = root / "tests" / "fixtures" / "_tmp_profile"
profile.mkdir(parents=True, exist_ok=True)
(profile / "Default" / "Network").mkdir(parents=True, exist_ok=True)
(profile / "Default" / "Network" / "Cookies").write_bytes(b"x" * 9000)
(profile / ".crosshub-session.json").write_text('{"ready": true}', encoding="utf-8")
data, manifest = pack_profile_essentials(
    profile,
    tenant_id=5,
    platform="temu",
    session_key="18061740604",
)
out = root / "tests" / "fixtures" / "minimal-profile-bundle.zip"
out.write_bytes(data)
print(out, len(data), manifest.get("bundle_sha256", "")[:16])
