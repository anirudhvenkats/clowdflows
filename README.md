# ClowdFlows Project (codename mothra) #

If you want to test the live installation of this tool, please check out http://clowdflows.org

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

### Optional: install extended requirements ###
```bash
cd clowdflows
pip install -r extended-requirements.txt
```

you need the extended requirements for some widgets to function.

### Configure project ###
```bash
cp mothra/__local_settings.py mothra/local_settings.py
vi mothra/local_settings.py
```

### Sync database ###
```bash
python manage.py syncdb
```

Warning: do not create a superuser yet!

### Migrate database ###
```bash
python manage.py migrate
```

### Create a superuser ###
```bash
python manage.py createsuperuser
```

### Populate your widget base ###
```bash
python manage.py auto_import_packages -n
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

For more info check out the wiki on github!
