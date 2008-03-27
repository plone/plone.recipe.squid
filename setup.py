from setuptools import setup, find_packages

version = '1.0b1'

setup(name='plone.recipe.squid',
      version=version,
      description="Buildout recipe to install squid",
      long_description=open("README.txt").read(),
      classifiers=[
        "Framework :: Buildout",
        "Framework :: Zope2",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: POSIX",
        "Topic :: Internet :: Proxy Servers",
        ],
      keywords='buildout squid cache proxy',
      author='Ricardo Newbery',
      author_email='ric@digitalmarbles.com',
      url='',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['plone','plone.recipe'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          # -*- Extra requirements: -*-
      ],
      entry_points={
          "zc.buildout" : [
              "build = plone.recipe.squid:BuildRecipe",
              "instance = plone.recipe.squid:ConfigureRecipe",
              ],
      }
      )

