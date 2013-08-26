#!/usr/bin/env python2

from distutils.core import setup

setup(name='xmlwiko',
      version='1.5',
      description='Generates XML files as input to ApacheForrest or Docbook from Wiki like input.',
      author='Dirk Baechle',
      author_email='dl9obn@darc.de',
      url='http://www.mydarc.de/dl9obn/programming/python/xmlwiko',
      packages=['xmlwiko'],
      package_dir={'' : 'src'},
      scripts = ['xmlwiko']
     )
