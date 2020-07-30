from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="prestio",
    version="0.0.4",
    description="Plone REST API IO tool",
    packages=["prestio"],
    package_data={"prestio": "prestio/prestio.cfg"},
    include_package_data=True,
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Operating System :: OS Independent",
    ],
    url="https://github.com/wobsta/prestio",
    author="André Wobst",
    author_email="project.prestio@wobsta.de",
    install_requires = [
        "requests",
        "click",
        "bs4",
        "lxml",
    ],
    entry_points = {
        'console_scripts': [
            'prestio = prestio.prestio:entry',
        ]
    },
)
