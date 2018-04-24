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
        'beautifulsoup4',
        'requests_oauthlib',
        'feedparser',
        'pandas',
        'numpy',
        'sqlalchemy',
        'dateutil'
    ],
    entry_points={'console_scripts': ['secparse=secparse.sec_parse:cli'],},
)
