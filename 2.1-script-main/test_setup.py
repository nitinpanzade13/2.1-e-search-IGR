"""
Test Setup - Verify all dependencies are installed correctly
"""
import sys

# Windows consoles default to cp1252, which cannot encode the tick marks
# below or the Devanagari place names in config.py. Without this the
# check dies on its own output before reporting anything.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def test_imports():
    """Test if all required packages can be imported."""
    
    print("=" * 70)
    print("TESTING SETUP - Dependency Check")
    print("=" * 70)
    
    packages = {
        "requests": ("requests", "HTTP client for web requests"),
        "bs4": ("beautifulsoup4", "BeautifulSoup for HTML parsing"),
        "lxml": ("lxml", "XML/HTML parser"),
        "openai": ("openai", "Vision model that reads the CAPTCHAs"),
        "PIL": ("pillow", "Cleans up the CAPTCHA before it is read"),
        "dotenv": ("python-dotenv", "Loads OPENAI_API_KEY from .env"),
    }

    results = {
        "success": [],
        "failed": []
    }

    for module, (package, description) in packages.items():
        try:
            __import__(module)
            print(f"✓ {package} ({description})")
            results["success"].append(package)

        except ImportError:
            print(f"✗ {package} - NOT INSTALLED ({description})")
            results["failed"].append(package)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"✓ Installed: {len(results['success'])}/{len(packages)}")
    print(f"✗ Missing: {len(results['failed'])}/{len(packages)}")
    
    if results["failed"]:
        print("\nTo install missing packages, run:")
        print("  pip install -r requirements.txt")
        return False
    else:
        print("\n🎉 All dependencies are installed correctly!")
        return True


def test_captcha_solver():
    """Check the CAPTCHA solver can load and preprocess an image."""

    print("\n" + "=" * 70)
    print("TESTING CAPTCHA SOLVER")
    print("=" * 70)

    try:
        import captcha_solver

        print(f"✓ Solver loaded")
        print(f"  {captcha_solver.banner()}")

        # Run a sample through the cleanup stage. This is local work, so
        # it proves the image pipeline without spending anything on the
        # API - only a real search can prove the reading itself.
        from pathlib import Path

        sample = Path(captcha_solver.CAPTCHA_PATH)

        if sample.exists():
            cleaned = captcha_solver._preprocess(sample.read_bytes())
            print(f"  Preprocessed {sample.name}: "
                  f"{len(sample.read_bytes())} -> {len(cleaned)} bytes")
        else:
            print(f"  ⚠ No {sample.name} to preprocess yet (not an error)")

        import os

        if not os.environ.get("OPENAI_API_KEY"):
            print("  ⚠ OPENAI_API_KEY is not set - CAPTCHAs will be typed by hand")
            print("    Put it in .env as OPENAI_API_KEY=sk-...")

        return True

    except Exception as e:
        print(f"✗ CAPTCHA solver failed to load: {e}")
        return False


def test_config():
    """Test if config.py is accessible."""
    
    print("\n" + "=" * 70)
    print("TESTING CONFIGURATION")
    print("=" * 70)
    
    try:
        import config
        
        print(f"✓ Config loaded")
        print(f"  Base URL: {config.BASE_URL}")
        print(f"  District: {config.DISTRICT}")
        print(f"  Taluka: {config.TALUKA}")
        print(f"  Village: {config.VILLAGE}")
        print(f"  Years: {config.YEARS[0]}-{config.YEARS[-1]}")
        print(f"  Survey numbers: {config.SURVEY_START}-{config.SURVEY_END}")
        print(f"  CAPTCHA mode: {config.CAPTCHA_MODE} ({config.OPENAI_MODEL})")
        print(f"  Output Directory: {config.OUTPUT_DIR}")
        print(f"  CSV files: {config.csv_path_for_year(config.YEARS[0])}")

        from pathlib import Path

        if not Path(".env").exists():
            print("\n  ⚠ No .env file - everything above is the shipped default")
            print("    copy .env.example .env, then: python setup_location.py")

        return True

    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        return False


def test_wifi_profiles():
    """
    Check the two rotation profiles actually exist on this machine.

    The names are per-PC, so a copy of this project arrives pointing at
    someone else's networks. Nothing complains until the portal's quota
    trips hours into a run and the switch silently fails.
    """

    print("\n" + "=" * 70)
    print("TESTING WI-FI ROTATION")
    print("=" * 70)

    import subprocess

    import config

    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "profiles"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=60,
        )
    except Exception:
        print("⚠ netsh unavailable - IP rotation only works on Windows")
        return True

    saved = {
        line.split(":", 1)[1].strip()
        for line in (result.stdout or "").splitlines()
        if ":" in line and "profile" in line.lower() and line.split(":", 1)[1].strip()
    }

    ok = True

    for label, profile in (
        ("Hotspot", config.HOTSPOT_PROFILE),
        ("Parking", config.PARKING_PROFILE),
    ):
        if profile in saved:
            print(f"✓ {label}: {profile}")
        else:
            ok = False
            print(f"⚠ {label}: {profile!r} is not saved on this PC")

    if not ok:
        print("\n  IP rotation will fail when the daily quota trips.")
        print("  Run `python setup_location.py --wifi` and set")
        print("  IGR_HOTSPOT_PROFILE / IGR_PARKING_PROFILE in .env")

    # A warning, not a failure - the scraper still works until the quota
    # runs out, and not everyone rotates at all.
    return True


def test_directories():
    """Test if required directories exist or can be created."""
    
    print("\n" + "=" * 70)
    print("TESTING DIRECTORY STRUCTURE")
    print("=" * 70)
    
    from pathlib import Path
    
    dirs = {
        "responses": "Output directory for saved HTML responses",
        "venv": "Virtual environment (optional)"
    }
    
    for dir_name, description in dirs.items():
        dir_path = Path(dir_name)
        
        if dir_path.exists():
            print(f"✓ {dir_name}/ - EXISTS ({description})")
        else:
            if dir_name == "venv":
                print(f"⚠ {dir_name}/ - NOT FOUND ({description})")
            else:
                try:
                    dir_path.mkdir(exist_ok=True)
                    print(f"✓ {dir_name}/ - CREATED ({description})")
                except Exception as e:
                    print(f"✗ {dir_name}/ - FAILED TO CREATE: {e}")
                    return False
    
    return True


def main():
    """Run all tests."""
    
    print("\n" + "=" * 70)
    print("IGR MAHARASHTRA PROPERTY SEARCH - SETUP VERIFICATION")
    print("=" * 70)
    print(f"Python Version: {sys.version}")
    print("=" * 70)
    
    tests = [
        ("Dependencies", test_imports),
        ("Configuration", test_config),
        ("Directories", test_directories),
        ("Wi-Fi rotation", test_wifi_profiles),
        ("CAPTCHA solver", test_captcha_solver),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ Test '{test_name}' failed with error: {e}")
            results[test_name] = False
    
    # Final summary
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 70)
    
    if all_passed:
        print("🎉 ALL TESTS PASSED - Setup is complete!")
        print("\nYou can now run:")
        print("  python search_property.py")
        print("or")
        print("  python batch_search.py")
    else:
        print("⚠ SOME TESTS FAILED - Please fix the issues above")
        print("\nCommon fixes:")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Check Python version (3.8+ required)")
        print("  - Verify config.py exists and is valid")
    
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
