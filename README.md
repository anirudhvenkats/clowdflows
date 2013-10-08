# ClowdFlows Project (codename mothra) #
## Prerequisites ##

- python >= 2.5
- pip
- virtualenv/wrapper (optional)

## Installation ##
### Creating the environment ###
Create a virtual python environment for the project.
If you're not using virtualenv or virtualenvwrapper you may skip this step.

#### For virtualenvwrapper ####
```bash
mkvirtualenv --no-site-packages mothra-env
```

#### For virtualenv ####
```bash
virtualenv --no-site-packages mothra-env
cd mothra-env
source bin/activate
```

### Clone the code ###
Obtain the url to your git repository.

```bash
git clone git@github.com:janezkranjc/clowdflows.git
```

### Install requirements ###
```bash
cd clowdflows
pip install -r requirements.txt
```

### Configure project ###
```bash
cp mothra/__local_settings.py mothra/local_settings.py
vi mothra/local_settings.py
```

### Sync database ###
```bash
python manage.py syncdb
```

### Migrate database ###
```bash
python manage.py migrate
```

## Running ##
```bash
python manage.py runserver
```

## Running with debugger ##
```bash
python manage.py runserver_plus
```

Open browser to http://127.0.0.1:8000
