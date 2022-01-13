from setuptools import setup

name='commode'

setup(
   name=name,
   version='1.0.1',
   description='Terminal client for Cabinet file server',
   author='Magnus Aa. Hirth',
   author_email='magnus.hirth@gmail.com',
   packages=[name],  #same as name
   install_requires=[
       'wheel',
       'click',
       'requests'
    ],
   scripts=['scripts/commode'],
)
