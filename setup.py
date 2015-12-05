from setuptools import setup, find_packages

setup(name='CSDschedule',version='0.0.1',author='David Little',
      packages=find_packages(),
      package_dir={'': 'src'},
      package_data={'': ['js']},
      requires=['numpy','pandas','pyrsistent'])
