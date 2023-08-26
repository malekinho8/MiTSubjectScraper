from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="MiTSubjectScraper",  # Make sure this is unique across PyPI
    version="0.1.0",
    author="Malek Ibrahim",
    author_email="malek.ibrahim02@gmail.com",
    description="A tool to scrape and analyze MIT course data.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/malekinho8/MiTSubjectScraper",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        "requests",
        "beautifulsoup4",
        "browser-cookie3",
        "pandas"
    ],
    entry_points={
        'console_scripts': [
            'mitscrape=MiTSubjectScraper.scrape:main',  # Assuming your main function is in 'main' of 'your_module_name.py'
            'mitanalyze=MiTSubjectScraper.analyze:main'
        ],
    },
)
