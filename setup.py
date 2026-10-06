from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in khanal_tech_integrations/__init__.py
from khanal_tech_integrations import __version__ as version

setup(
	name="khanal_tech_integrations",
	version=version,
	description="Integrations of Khanal Tech for Khanal Foods",
	author="Khanal Tech",
	author_email="lian@khanalfoods.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
