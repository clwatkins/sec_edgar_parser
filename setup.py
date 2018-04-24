from setuptools import setup

setup(
    name='SECParse',
    version='0.7',
    description='Tools to parse the SEC\'s Edgar database.',
    author='Chris Watkins',
    author_email = 'chris.watkins93@gmail.com',
    license = 'MIT',
    packages=['secparse'],
    install_requires=[
        'Click',
        'python-dateutil',
        'requests',
        'requests_oauthlib',
        'feedparser',
        'xlwings',
        'pandas',
        'numpy',
    ],
    entry_points={'console_scripts': ['secparse=secparse.main:cli'],},
)
