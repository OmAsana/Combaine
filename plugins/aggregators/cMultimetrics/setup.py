"""
cMultimetrics its like multi_metrics.py but writen in C
"""
from setuptools import setup, Extension

setup(
    name="cMultimetrics",
    version=0.1,
    description="cMultimetrics its like multi_metrics.py but writen in C",
    author="Sergey (sakateka) Kacheev",
    test_suite="test.cMultimetrics_unittest",
    ext_modules=[
        Extension(
            'cMultimetrics',
            ['src/cMultimetrics.c']
        )
    ]
)
