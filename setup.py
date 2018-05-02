from setuptools import setup

setup(
    name='SECParse',
    version='0.7',
    description='Tools to parse the SEC\'s Edgar database.',
    author='Chris Watkins',
    author_email='chris.watkins93@gmail.com',
    license='MIT',
    packages=['secparse'],
    install_requires=[
        'Click',
        'python-dateutil',
        'requests',
        'urllib3',
        'beautifulsoup4',
        'requests_oauthlib',
        'feedparser',
        'xlrd',
        'pandas',
        'numpy',
        'sqlalchemy',
    ],
    entry_points={'console_scripts': ['secparse=secparse.sec_parse:cli'], },
)
