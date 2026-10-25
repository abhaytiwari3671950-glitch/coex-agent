import os
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('COEX_ENV', 'production') == 'development'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY before running production.')
    SECRET_KEY = 'development-only-not-for-hosted-deployments'
deployment_hosts = [os.environ.get(key, '') for key in ('VERCEL_URL', 'VERCEL_BRANCH_URL', 'VERCEL_PROJECT_PRODUCTION_URL')]
configured_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1' if DEBUG else '').split(',')
ALLOWED_HOSTS = list(dict.fromkeys(host.strip() for host in configured_hosts + deployment_hosts if host.strip()))
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([x.strip() for x in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if x.strip()] + ['https://' + host for host in deployment_hosts if host]))
database_url = os.environ.get('DATABASE_URL', '')
if not DEBUG and not database_url.startswith(('postgres://', 'postgresql://')):
    raise ImproperlyConfigured('Production requires persistent PostgreSQL DATABASE_URL.')
DATABASES = {'default': dj_database_url.parse(database_url, conn_max_age=0, ssl_require=not DEBUG) if database_url else {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR / 'db.sqlite3'}}
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.staticfiles', 'chat']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'chat.middleware.PrivateResponses']
ROOT_URLCONF = 'coex.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth']}}]
WSGI_APPLICATION = 'coex.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 8 * 3600
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
# Enable only behind a proxy that strips and sets this header.
if os.environ.get('VERCEL') == '1' or os.environ.get('TRUST_PROXY_HTTPS') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')
AUTH_PASSWORD_VALIDATORS = [
 {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
 {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':10}},
 {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
 {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LOGIN_URL = '/login/'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024
GEMINI_MODEL = 'gemini-3.5-flash-lite'
GOOGLE_GENERATIVE_AI_API_KEY = os.environ.get('GOOGLE_GENERATIVE_AI_API_KEY', '')
DAILY_USER_MESSAGES = int(os.environ.get('DAILY_USER_MESSAGES','50'))
DAILY_SITE_MESSAGES = int(os.environ.get('DAILY_SITE_MESSAGES','500'))
