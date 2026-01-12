from pathlib import Path
import os
from decouple import config


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = config('SECRET_KEY', default='django-insecure-default-key')

# DEBUG harus False di production
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = [
    '10.130.223.45',
    '127.0.0.1',
    'localhost',
    # Tambahkan IP atau domain server jika perlu
]

# Application definition 
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'material_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # <-- penting untuk static file
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'data_materials.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'data_materials.wsgi.application'




# Database
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE'),
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', cast=int),
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
        },
    },
    'pcs_year': {
        'ENGINE': config('YEAR_DB_ENGINE'),
        'NAME': config('YEAR_DB_NAME'),
        'USER': config('YEAR_DB_USER'),
        'PASSWORD': config('YEAR_DB_PASSWORD'),
        'HOST': config('YEAR_DB_HOST'),
        'PORT': config('YEAR_DB_PORT', cast=int),
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
        },
    }
}



# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",  # ini untuk development
]
STATIC_ROOT = BASE_DIR / "staticfiles"  # ini untuk production / collectstatic

# Gunakan WhiteNoise untuk compress & cache
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'


# Login settings
LOGIN_REDIRECT_URL = 'MATERIAL'
LOGIN_URL = 'login'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
