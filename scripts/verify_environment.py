"""
Environment verification script for the Intelligent Document Processing System.

Run with:
    python scripts/verify_environment.py

Checks that every required dependency actually imports (not just installs),
that the spaCy model loads, and that Neo4j is reachable if credentials are
present in .env. Prints a clear PASS/FAIL report and does not fabricate
results — a failed check is reported as FAIL with the real error message.
"""

import sys
import os

results = []


def check(name, fn):
    try:
        fn()
        results.append((name, True, None))
    except Exception as e:
        results.append((name, False, str(e)))


def check_python():
    assert sys.version_info >= (3, 9), f"Python {sys.version} is too old (need 3.9+)"


def check_pymupdf():
    import pymupdf  # noqa: F401


def check_docx():
    import docx  # noqa: F401


def check_xlsx():
    import openpyxl  # noqa: F401


def check_pandas():
    import pandas  # noqa: F401


def check_bs4():
    from bs4 import BeautifulSoup  # noqa: F401


def check_spacy():
    import spacy  # noqa: F401


def check_spacy_model():
    import spacy
    spacy.load("en_core_web_sm")


def check_paddleocr():
    from paddleocr import PaddleOCR  # noqa: F401


def check_neo4j_driver():
    from neo4j import GraphDatabase  # noqa: F401


def check_rapidfuzz():
    from rapidfuzz import fuzz  # noqa: F401


def check_pillow():
    from PIL import Image  # noqa: F401


def check_opencv():
    import cv2  # noqa: F401


def check_neo4j_connection():
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    password = os.environ.get("NEO4J_PASSWORD")

    if not (uri and user and password):
        raise RuntimeError(
            "NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD not set (skip if Neo4j "
            "isn't running yet — this is expected before Phase 5)"
        )

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
    finally:
        driver.close()


def main():
    # Load .env if python-dotenv is available; otherwise rely on real env vars.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    checks = [
        ("Python", check_python),
        ("PyMuPDF", check_pymupdf),
        ("python-docx", check_docx),
        ("openpyxl", check_xlsx),
        ("pandas", check_pandas),
        ("BeautifulSoup", check_bs4),
        ("spaCy", check_spacy),
        ("spaCy model (en_core_web_sm)", check_spacy_model),
        ("PaddleOCR", check_paddleocr),
        ("Neo4j driver", check_neo4j_driver),
        ("RapidFuzz", check_rapidfuzz),
        ("Pillow", check_pillow),
        ("OpenCV", check_opencv),
        ("Neo4j connection", check_neo4j_connection),
    ]

    for name, fn in checks:
        check(name, fn)

    print("## ENVIRONMENT CHECK\n")
    all_passed = True
    for name, passed, error in results:
        status = "PASS" if passed else "FAIL"
        print(f"{name}: {status}")
        if not passed:
            print(f"    -> {error}")
            all_passed = False

    print(f"\nOverall: {'PASS' if all_passed else 'FAIL (see details above)'}")

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
