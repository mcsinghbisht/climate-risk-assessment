#!/usr/bin/env python
"""Test script to verify all dependencies are installed correctly."""

import sys
import os

os.chdir(os.path.dirname(__file__))

# List of packages to test
PACKAGES = {
    'pandas': 'Data processing',
    'numpy': 'Numerical computing',
    'geopandas': 'Geospatial data',
    'shapely': 'Geometric operations',
    'pyproj': 'Coordinate transformations',
    'sqlalchemy': 'Database ORM',
    'requests': 'HTTP requests',
    'requests_cache': 'Request caching',
    'apscheduler': 'Job scheduling',
    'pytz': 'Timezone handling',
    'dotenv': 'Environment variables',
    'pytest': 'Testing framework',
    'pythonjsonlogger': 'JSON logging',
}

def test_imports():
    """Test importing all required packages."""
    print("Testing imports...")
    print("-" * 60)

    failed = []
    for package, description in PACKAGES.items():
        try:
            __import__(package)
            status = "[OK]"
            print(f"{status} {package:20} - {description}")
        except ImportError as e:
            status = "[FAIL]"
            print(f"{status} {package:20} - {str(e)}")
            failed.append(package)

    print("-" * 60)
    if not failed:
        print("\n[SUCCESS] ALL IMPORTS SUCCESSFUL!")
        return True
    else:
        print(f"\n[FAILED] Failed imports: {', '.join(failed)}")
        return False

if __name__ == '__main__':
    success = test_imports()
    sys.exit(0 if success else 1)
