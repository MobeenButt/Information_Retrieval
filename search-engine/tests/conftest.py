"""Pytest configuration: make the ``src`` package importable from the tests."""
import os
import sys

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
SRC_DIR = os.path.abspath(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
