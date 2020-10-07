# finance
A [CS50 project](https://cs50.harvard.edu/x/2020/tracks/web/finance/) - Flask application that simulates stock trading with real stock data

## Setting up a development environment

1. Clone the repository

```
git clone git@github.com:tomwhross/finance.git
cd finance/
```

2. Optionally setup a virtual environment

```
python -m venv .
source bin/activate
```

3. Install the requirements

```
pip install -r requirements.txt
```

4. Set the Flask app environment variable

```
export FLASK_APP=application.py
```

5. Set the IEXCloud API key (Register for a free plan [here](https://iexcloud.io/cloud-login#/register/))

```
export API_KEY=<iexcloud_api_key>
```

6. Start the development server

```
flask run
```
