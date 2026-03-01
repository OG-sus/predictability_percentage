from setuptools import setup, find_packages

setup(
    name="predictability_score",
    version="1.0.0",
    description="The Predictability Score™: An institutional-grade analytics engine for quantifying data stability.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Predictability API Team",
    author_email="support@predictability-api.com",
    url="https://predictability-api.com",
    license="Proprietary",  # Modern license declaration
    py_modules=["fsr", "sliding_window"],
    install_requires=[
        "numpy",
        "numba",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        # "License :: Proprietary" is deprecated, so we remove it from here.
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Mathematics",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires='>=3.8',
)
