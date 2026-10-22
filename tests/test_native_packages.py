import pathlib
import unittest
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parents[1]


class NativePackageTests(unittest.TestCase):
    def test_download_assets_load_after_app_and_before_bootstrap(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertLess(html.index('/app.js'), html.index('/native-apps.js'))
        self.assertLess(html.index('/native-apps.js'), html.index('/meetings.js'))
        self.assertIn('/native-apps.css', html)

    def test_public_download_names_match_release_assets(self):
        javascript = (ROOT / "static" / "native-apps.js").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "native-apps.yml").read_text(encoding="utf-8")
        for filename in ("NJA-System-Windows.exe", "NJA-System-Android.apk"):
            self.assertIn(f"/releases/latest/download/{filename}", javascript)
            self.assertIn(f"dist/{filename}", workflow)
        self.assertIn('--repo "$GITHUB_REPOSITORY"', workflow)

    def test_android_manifest_is_secure_and_call_ready(self):
        manifest_path = ROOT / "packaging" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
        root = ET.parse(manifest_path).getroot()
        android = "{http://schemas.android.com/apk/res/android}"
        permissions = {item.attrib[f"{android}name"] for item in root.findall("uses-permission")}
        self.assertIn("android.permission.CAMERA", permissions)
        self.assertIn("android.permission.RECORD_AUDIO", permissions)
        application = root.find("application")
        self.assertEqual("false", application.attrib[f"{android}usesCleartextTraffic"])

    def test_windows_package_targets_self_contained_x64(self):
        project = ET.parse(ROOT / "packaging" / "windows" / "NjaSystem.Windows.csproj").getroot()
        values = {child.tag: child.text for group in project.findall("PropertyGroup") for child in group}
        self.assertEqual("win-x64", values["RuntimeIdentifier"])
        self.assertEqual("true", values["SelfContained"])
        self.assertEqual("true", values["PublishSingleFile"])


if __name__ == "__main__":
    unittest.main()
