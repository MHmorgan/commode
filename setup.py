from setuptools import setup
from commode import version

name='commode'

setup(
   name=name,
   version=version,
   description='Terminal client for Cabinet file server',
   author='Magnus Aa. Hirth',
   author_email='magnus.hirth@gmail.com',
   packages=[name],  #same as name
   install_requires=[
       'wheel',
       'click',
       'requests',
       'jinja2'
    ],
   scripts=['scripts/commode'],
)
